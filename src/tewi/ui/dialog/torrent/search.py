from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from ....util.log import log_time
from ...messages import SearchCompletedEvent
from ...util import subtitle_keys


class SearchDialog(ModalScreen):
    @log_time
    def compose(self) -> ComposeResult:
        yield SearchWidget()


class SearchWidget(Static):
    BINDINGS = [
        Binding("enter", "search", "[Search] Search", priority=True),
        Binding("escape", "close", "[Search] Close"),
    ]

    @log_time
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Enter search term...", id="search-input")

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Search"
        self.border_subtitle = subtitle_keys(
            ("Enter", "Search"), ("ESC", "Close")
        )
        self.query_one("#search-input").focus()

    @log_time
    def action_search(self) -> None:
        value = self.query_one("#search-input").value

        self.post_message(SearchCompletedEvent(value))
        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
