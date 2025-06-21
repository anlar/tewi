
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea
from textual.app import ComposeResult

from ....message import TorrentLabelsUpdated


class UpdateTorrentLabelsDialog(ModalScreen):

    def __init__(self, torrent, torrent_ids):
        self.torrent = torrent
        self.torrent_ids = torrent_ids
        super().__init__()

    def compose(self) -> ComposeResult:
        yield UpdateTorrentLabelsWidget(self.torrent, self.torrent_ids)


class UpdateTorrentLabelsWidget(Static):

    BINDINGS = [
            Binding("enter", "update", "[Torrent] Update labels", priority=True),
            Binding("escape", "close", "[Torrent] Close"),
            ]

    def __init__(self, torrent, torrent_ids):
        self.torrent = torrent
        self.torrent_ids = torrent_ids
        super().__init__()

    def compose(self) -> ComposeResult:
        yield TextArea()

    def on_mount(self) -> None:
        self.border_title = 'Update torrent labels (comma-separated list)'
        self.border_subtitle = '(Enter) Update / (ESC) Close'

        text_area = self.query_one(TextArea)

        if self.torrent and len(self.torrent.labels) > 0:
            text_area.load_text(", ".join(self.torrent.labels))

        text_area.cursor_location = text_area.document.end

    def action_update(self) -> None:
        value = self.query_one(TextArea).text

        if self.torrent:
            torrent_ids = [self.torrent.id]
        else:
            torrent_ids = self.torrent_ids

        self.post_message(TorrentLabelsUpdated(
            torrent_ids, value))

        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)
