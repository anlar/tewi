"""Tests for add torrent dialog reading link from clipboard."""

import asyncio
import threading
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import TextArea

import src.tewi.ui.dialog.torrent.add as add_module
from src.tewi.ui.dialog.torrent.add import AddTorrentDialog

MAGNET = "magnet:?xt=urn:btih:" + "a" * 40


class AddApp(App):
    def __init__(self, web: bool = False) -> None:
        super().__init__()
        self.web = web

    @property
    def is_web(self) -> bool:
        return self.web

    def on_mount(self) -> None:
        self.push_screen(AddTorrentDialog("/data", 1024))


def run_dialog(
    clipboard_text: str | None, *, web: bool = False, typed: str = ""
) -> tuple[str, list]:
    """Open dialog, type text while clipboard is read and return text
    shown in dialog with threads clipboard was read from."""
    threads = []
    read = threading.Event()

    def fake_paste() -> str | None:
        threads.append(threading.current_thread())
        # Clipboard answers after user typed text
        read.wait(5)
        return clipboard_text

    async def run() -> str:
        app = AddApp(web)
        async with app.run_test() as pilot:
            await pilot.pause()
            if typed:
                await pilot.press(*typed)
            read.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            return app.screen.query_one(TextArea).text

    with patch.object(add_module.clipboard, "paste", fake_paste):
        text = asyncio.run(run())

    return text, threads


def test_link_from_clipboard_is_read_in_background():
    text, threads = run_dialog(MAGNET)

    assert text == MAGNET
    assert len(threads) == 1
    assert threads[0] is not threading.main_thread()


@pytest.mark.parametrize("clipboard_text", [None, "", "some text"])
def test_default_text_without_link_in_clipboard(clipboard_text):
    text, _ = run_dialog(clipboard_text)

    assert text == "~/"


def test_link_from_clipboard_does_not_replace_typed_text():
    text, _ = run_dialog(MAGNET, typed="x")

    assert text == "~/x"


def test_clipboard_is_not_read_in_web_mode():
    text, threads = run_dialog(MAGNET, web=True)

    assert text == "~/"
    assert threads == []
