
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Label
from textual.app import ComposeResult

from ....message import EditTorrentCommand
from ....util.decorator import log_time


class EditTorrentDialog(ModalScreen):

    @log_time
    def __init__(self, torrent):
        self.torrent = torrent
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield EditTorrentWidget(self.torrent)


class EditTorrentWidget(Static):

    BINDINGS = [
            Binding("enter", "update", "[Torrent] Update", priority=True),
            Binding("escape", "close", "[Torrent] Close"),
            ]

    @log_time
    def __init__(self, torrent):
        self.torrent = torrent
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield Label("[bold]Name:[/]")
        yield Input(id="name-input",
                    placeholder="Torrent name...")
        yield Label("[bold]Location:[/]")
        yield Input(id="location-input",
                    placeholder="Torrent location...")

    @log_time
    def on_mount(self) -> None:
        self.border_title = 'Edit torrent'
        self.border_subtitle = ('(Enter) Update / '
                                '(Tab) Switch field / '
                                '(ESC) Close')

        name_input = self.query_one("#name-input", Input)
        location_input = self.query_one("#location-input", Input)

        name_input.value = self.torrent.name
        location_input.value = self.torrent.download_dir

        name_input.focus()

    @log_time
    def action_update(self) -> None:
        name_input = self.query_one("#name-input", Input)
        location_input = self.query_one("#location-input", Input)

        new_name = name_input.value.strip()
        new_location = location_input.value.strip()

        if not new_name:
            return

        if not new_location:
            return

        self.post_message(EditTorrentCommand(
            self.torrent.id, new_name, new_location))

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
