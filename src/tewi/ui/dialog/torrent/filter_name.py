from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from ....util.log import log_time
from ...messages import FilterNameUpdatedEvent
from ...util import subtitle_keys


class FilterNameDialog(ModalScreen):
    @log_time
    def compose(self) -> ComposeResult:
        yield FilterNameWidget()


class FilterNameWidget(Static):
    BINDINGS = [
        Binding("enter", "filter", "[Torrent] Filter", priority=True),
        Binding("escape", "close", "[Torrent] Close"),
    ]

    @log_time
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Enter torrent name...", id="filter-name-input")

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Filter by name"
        self.border_subtitle = subtitle_keys(
            ("Enter", "Filter"), ("ESC", "Close")
        )
        self.query_one("#filter-name-input").focus()

    @log_time
    def action_filter(self) -> None:
        value = self.query_one("#filter-name-input").value

        self.post_message(FilterNameUpdatedEvent(value))
        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
