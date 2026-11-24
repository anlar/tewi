"""Tests for copying magnet links of torrents in torrent list."""

import asyncio
from dataclasses import replace
from unittest.mock import patch

from textual import on
from textual.app import App, ComposeResult

import src.tewi.ui.panel.listview as listview_module
from src.tewi.ui.messages import Notification
from src.tewi.ui.panel.listview import TorrentListViewPanel
from tests.tewi.ui.helpers import make_list_panel, make_torrent

HASH_A = "a" * 40
HASH_B = "b" * 40
HASH_C = "c" * 40

TORRENTS = [
    replace(make_torrent("first one"), hash=HASH_A),
    replace(make_torrent("second"), hash=HASH_B),
    replace(make_torrent("third"), hash=HASH_C),
]


class ListApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.notifications: list[Notification] = []
        self.copied: list[str] = []

    def compose(self) -> ComposeResult:
        yield make_list_panel(100)

    def on_mount(self) -> None:
        self.panel.focus()

    @property
    def panel(self) -> TorrentListViewPanel:
        return self.query_one(TorrentListViewPanel)

    def copy_to_clipboard(self, text: str) -> None:
        self.copied.append(text)

    @on(Notification)
    def record(self, message: Notification) -> None:
        self.notifications.append(message)


def run_list(test, torrents=TORRENTS) -> list[str]:
    """Run test and return texts sent to system clipboard."""
    system_copied: list[str] = []

    async def run() -> None:
        app = ListApp()
        async with app.run_test(size=(100, 20)) as pilot:
            app.panel.r_torrents = list(torrents)
            await pilot.pause()
            await test(app, pilot)

    with patch.object(
        listview_module.clipboard,
        "copy",
        side_effect=lambda text: system_copied.append(text) or True,
    ):
        asyncio.run(run())

    return system_copied


def magnet(info_hash: str, name: str) -> str:
    return f"magnet:?xt=urn:btih:{info_hash}&dn={name}"


def test_copies_highlighted_torrent_without_marks():
    async def test(app, pilot):
        await pilot.press("M")

        assert app.copied == [magnet(HASH_A, "first%20one")]
        assert [n.message for n in app.notifications] == ["Copied magnet link"]

    system_copied = run_list(test)
    assert system_copied == [magnet(HASH_A, "first%20one")]


def test_copies_marked_torrents_one_per_line_in_list_order():
    async def test(app, pilot):
        # Mark third, then first: copy keeps list order
        await pilot.press("G", "space", "g", "space", "M")

        assert app.copied == [
            magnet(HASH_A, "first%20one") + "\n" + magnet(HASH_C, "third")
        ]
        assert [n.message for n in app.notifications] == [
            "Copied 2 magnet links"
        ]

    run_list(test)


def test_skips_torrents_with_invalid_hash():
    torrents = [TORRENTS[0], make_torrent("broken")]

    async def test(app, pilot):
        await pilot.press("V", "M")

        assert app.copied == [magnet(HASH_A, "first%20one")]
        assert [(n.message, n.severity) for n in app.notifications] == [
            ("Copied magnet link, skipped 1", "warning")
        ]

    run_list(test, torrents)


def test_warns_when_no_link_can_be_built():
    async def test(app, pilot):
        await pilot.press("M")

        assert app.copied == []
        assert [(n.message, n.severity) for n in app.notifications] == [
            ("No magnet links to copy", "warning")
        ]

    system_copied = run_list(test, [make_torrent("broken")])
    assert system_copied == []
