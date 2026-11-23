from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from ....torrent.models import Torrent
from ....util.log import log_time
from ...messages import TorrentLabelsUpdatedEvent
from ...util import subtitle_keys


class UpdateTorrentLabelsDialog(ModalScreen):
    @log_time
    def __init__(self, torrents: list[Torrent]):
        self.torrents = torrents
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield UpdateTorrentLabelsWidget(self.torrents)


class UpdateTorrentLabelsWidget(Static):
    BINDINGS = [
        Binding("enter", "update", "[Torrent] Update labels", priority=True),
        Binding("escape", "close", "[Torrent] Close"),
    ]

    @log_time
    def __init__(self, torrents: list[Torrent]):
        """
        Args:
            torrents: Torrents to set labels (replacing current ones) to
        """
        self.torrents = torrents
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield TextArea()

    @log_time
    def on_mount(self) -> None:
        if len(self.torrents) == 1:
            self.border_title = "Update torrent labels (comma-separated list)"
        else:
            self.border_title = (
                f"Set labels of {len(self.torrents)} torrents "
                "(comma-separated list)"
            )
        self.border_subtitle = subtitle_keys(
            ("Enter", "Update"), ("ESC", "Close")
        )

        text_area = self.query_one(TextArea)

        # Labels replace current ones, so they are prefilled only if all
        # torrents have the same labels
        labels = self.torrents[0].labels
        if labels and all(t.labels == labels for t in self.torrents):
            text_area.load_text(", ".join(labels))

        text_area.cursor_location = text_area.document.end

    @log_time
    def action_update(self) -> None:
        value = self.query_one(TextArea).text

        self.post_message(
            TorrentLabelsUpdatedEvent([t.hash for t in self.torrents], value)
        )

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
