# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for copying magnet links of torrents in torrent list."""

import asyncio
from dataclasses import replace

from textual import on
from textual.app import App, ComposeResult

from src.tewi.ui.messages import CopyToClipboardCommand, Notification
from src.tewi.ui.panel.listview import TorrentListViewPanel
from tests.tewi.ui.helpers import make_list_panel, make_torrent

NAMES = ["first one", "second", "third", "fourth", "fifth"]
TORRENTS = [
    replace(make_torrent(name), hash=str(i) * 40, hash_v1=str(i) * 40)
    for i, name in enumerate(NAMES)
]


class ListApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.notifications: list[tuple[str, str]] = []
        self.copies: list[CopyToClipboardCommand] = []

    def compose(self) -> ComposeResult:
        yield make_list_panel(100)

    def on_mount(self) -> None:
        self.panel.focus()

    @property
    def panel(self) -> TorrentListViewPanel:
        return self.query_one(TorrentListViewPanel)

    @on(CopyToClipboardCommand)
    def record_copy(self, message: CopyToClipboardCommand) -> None:
        self.copies.append(message)

    @on(Notification)
    def record_notification(self, message: Notification) -> None:
        self.notifications.append((message.message, message.severity))


def run_list(test, torrents=TORRENTS) -> None:
    async def run() -> None:
        app = ListApp()
        async with app.run_test(size=(100, 20)) as pilot:
            app.panel.r_torrents = list(torrents)
            await pilot.pause()
            await test(app, pilot)

    asyncio.run(run())


def magnet(idx: int) -> str:
    name = NAMES[idx].replace(" ", "%20")
    return f"magnet:?xt=urn:btih:{str(idx) * 40}&dn={name}"


def test_copies_highlighted_torrent_without_marks():
    async def test(app, pilot):
        await pilot.press("j", "M")

        assert app.copies == [CopyToClipboardCommand(magnet(1), "magnet link")]
        assert app.notifications == []

    run_list(test)


def test_copies_marked_torrents_one_per_line_in_list_order():
    async def test(app, pilot):
        # Mark in reverse order: copy keeps list order
        await pilot.press("G", "space", "k", "k", "space")
        await pilot.press("g", "space", "M")

        assert app.copies == [
            CopyToClipboardCommand(
                "\n".join([magnet(0), magnet(2), magnet(4)]),
                "3 magnet links",
            )
        ]

    run_list(test)


def test_uses_v1_info_hash_of_hybrid_torrent():
    # Torrent ID is truncated v2 info hash
    hybrid = replace(TORRENTS[0], hash="f" * 40)

    async def test(app, pilot):
        await pilot.press("M")

        assert app.copies == [CopyToClipboardCommand(magnet(0), "magnet link")]

    run_list(test, [hybrid])


def test_skips_v2_only_torrents():
    v2_only = replace(make_torrent("v2"), hash="f" * 40, hash_v1=None)
    torrents = [TORRENTS[0], v2_only]

    async def test(app, pilot):
        await pilot.press("V", "M")

        assert app.copies == [CopyToClipboardCommand(magnet(0), "magnet link")]
        assert app.notifications == [
            ("Skipped torrents without v1 info hash: 1", "warning")
        ]

    run_list(test, torrents)


def test_warns_when_no_link_can_be_built():
    async def test(app, pilot):
        await pilot.press("M")

        assert app.copies == []
        assert app.notifications == [("No magnet links to copy", "warning")]

    run_list(test, [replace(make_torrent("v2"), hash_v1=None)])
