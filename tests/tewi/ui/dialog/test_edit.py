# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for torrent edit dialog."""

import asyncio
from dataclasses import replace

import pytest
from textual.app import App
from textual.widgets import Input

from src.tewi.ui.dialog.torrent.edit import EditTorrentDialog
from src.tewi.ui.messages import EditTorrentCommand
from tests.tewi.ui.helpers import make_torrent


class EditApp(App):
    def __init__(self, torrents) -> None:
        super().__init__()
        self.torrents = torrents
        self.commands = []

    def on_mount(self) -> None:
        self.push_screen(EditTorrentDialog(self.torrents))

    def on_edit_torrent_command(self, event: EditTorrentCommand) -> None:
        self.commands.append(event)


@pytest.mark.parametrize(
    "locations,expected",
    [
        (["/a"], "/a"),
        (["/a", "/a"], "/a"),
        # Unchanged location would move second torrent to /a
        (["/a", "/b"], ""),
    ],
)
def test_location_is_prefilled_only_if_shared(locations, expected):
    torrents = [
        replace(make_torrent(str(i)), download_dir=location)
        for i, location in enumerate(locations)
    ]

    async def run() -> None:
        app = EditApp(torrents)
        async with app.run_test() as pilot:
            await pilot.pause()
            location = app.screen.query_one("#location-input", Input)
            assert location.value == expected

            await pilot.press("enter")
            await pilot.pause()

            if expected:
                (command,) = app.commands
                name = "0" if len(torrents) == 1 else None
                assert (command.name, command.location) == (name, expected)
            else:
                assert app.commands == []

    asyncio.run(run())
