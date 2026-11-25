# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

from tewi.torrent.models import Torrent

from ....util.log import log_time
from ...messages import EditTorrentCommand
from ...util import subtitle_keys


class EditTorrentDialog(ModalScreen[None]):
    @log_time
    def __init__(self, torrents: list[Torrent]):
        self.torrents = torrents
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield EditTorrentWidget(self.torrents)


class EditTorrentWidget(Static):
    BINDINGS = [
        Binding("enter", "update", "[Torrent] Update", priority=True),
        Binding("escape", "close", "[Torrent] Close"),
    ]

    @log_time
    def __init__(self, torrents: list[Torrent]):
        """
        Args:
            torrents: Torrents to edit: several torrents can only be moved
                to new location, keeping their names
        """
        self.torrents = torrents
        self.edit_name = len(torrents) == 1
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        if self.edit_name:
            yield Label("[bold]Name:[/]")
            yield Input(id="name-input", placeholder="Torrent name...")
        yield Label("[bold]Location:[/]")
        yield Input(id="location-input", placeholder="Torrent location...")

    @log_time
    def on_mount(self) -> None:
        # Prefilled only if all torrents have the same location: Enter on
        # empty location does nothing, so unchanged value doesn't move data
        # of other torrents to location of the first one
        location = self.torrents[0].download_dir
        location_input = self.query_one("#location-input", Input)
        if all(t.download_dir == location for t in self.torrents):
            location_input.value = location

        if self.edit_name:
            self.border_title = "Edit torrent"
            self.border_subtitle = subtitle_keys(
                ("Enter", "Update"), ("Tab", "Switch field"), ("ESC", "Close")
            )

            name_input = self.query_one("#name-input", Input)
            name_input.value = self.torrents[0].name
            name_input.focus()
        else:
            self.border_title = f"Move {len(self.torrents)} torrents"
            self.border_subtitle = subtitle_keys(
                ("Enter", "Move"), ("ESC", "Close")
            )

            location_input.focus()

    @log_time
    def action_update(self) -> None:
        location_input = self.query_one("#location-input", Input)
        new_location = location_input.value.strip()

        if not new_location:
            return

        if self.edit_name:
            name_input = self.query_one("#name-input", Input)
            new_name = name_input.value.strip()

            if not new_name:
                return
        else:
            new_name = None

        self.post_message(
            EditTorrentCommand(self.torrents, new_name, new_location)
        )

        cast(ModalScreen[None], self.parent).dismiss()

    @log_time
    def action_close(self) -> None:
        cast(ModalScreen[None], self.parent).dismiss()
