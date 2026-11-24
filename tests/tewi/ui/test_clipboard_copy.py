"""Tests for copying text to terminal and system clipboard."""

import asyncio
import threading
from unittest.mock import patch

import pytest
from textual.app import App

import src.tewi.app as app_module
from src.tewi.app import CLIPBOARD_MAX_SIZE, MainApp
from src.tewi.ui.messages import CopyToClipboardCommand, Notification


class ClipboardApp(App):
    """App running MainApp clipboard methods with fake system clipboard."""

    copy_to_clipboard = MainApp.copy_to_clipboard
    copy_text = MainApp.copy_text
    copy_to_system_clipboard = MainApp.copy_to_system_clipboard
    handle_copy_to_clipboard_command = MainApp.handle_copy_to_clipboard_command

    def __init__(self, web: bool = False) -> None:
        super().__init__()
        self.web = web
        self.notifications = []

    @property
    def is_web(self) -> bool:
        return self.web

    def on_notification(self, event: Notification) -> None:
        self.notifications.append((event.message, event.severity))


def run_copy(
    action, *, available=True, copied=True, web=False
) -> tuple[ClipboardApp, list]:
    """Run action and return app with texts sent to system clipboard
    (with thread they were sent from)."""
    system = []

    def fake_copy(text: str) -> bool:
        system.append((text, threading.current_thread()))
        return copied

    async def run() -> ClipboardApp:
        app = ClipboardApp(web)
        async with app.run_test() as pilot:
            action(app)
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
        return app

    with (
        patch.object(app_module.clipboard, "is_available", lambda: available),
        patch.object(app_module.clipboard, "copy", fake_copy),
    ):
        app = asyncio.run(run())

    return app, system


def command(app: ClipboardApp, text: str = "magnet:?x") -> None:
    app.post_message(CopyToClipboardCommand(text, "magnet link"))


def test_command_copies_to_both_clipboards_in_background():
    app, system = run_copy(command)

    assert app.clipboard == "magnet:?x"
    assert [text for text, _ in system] == ["magnet:?x"]
    assert system[0][1] is not threading.main_thread()
    assert app.notifications == [("Copied magnet link", "information")]


def test_command_reports_terminal_only_when_system_copy_fails():
    app, system = run_copy(command, copied=False)

    assert app.clipboard == "magnet:?x"
    assert app.notifications == [
        ("Sent magnet link to terminal clipboard", "information")
    ]


@pytest.mark.parametrize(
    "available,web", [(False, False), (True, True)], ids=["ssh", "web"]
)
def test_command_skips_system_clipboard_of_other_machine(available, web):
    app, system = run_copy(command, available=available, web=web)

    assert app.clipboard == "magnet:?x"
    assert system == []
    assert app.notifications == [
        ("Sent magnet link to terminal clipboard", "information")
    ]


def test_command_refuses_text_too_large_for_clipboard():
    app, system = run_copy(
        lambda app: command(app, "x" * (CLIPBOARD_MAX_SIZE + 1))
    )

    assert app.clipboard == ""
    assert system == []
    assert app.notifications == [
        (
            "Failed to copy magnet link:\ntoo large for clipboard (524.29 kB)",
            "warning",
        )
    ]


def test_textual_copy_uses_system_clipboard_without_notification():
    app, system = run_copy(lambda app: app.copy_to_clipboard("selected"))

    assert app.clipboard == "selected"
    assert [text for text, _ in system] == ["selected"]
    assert app.notifications == []
