from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Input
from textual.app import ComposeResult

from ....message import SearchTorrent


class SearchDialog(ModalScreen):

    def compose(self) -> ComposeResult:
        yield SearchWidget()


class SearchWidget(Static):

    BINDINGS = [
            Binding("enter", "search", "[Search] Search", priority=True),
            Binding("escape", "close", "[Search] Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Enter search term...", id="search-input")

    def on_mount(self) -> None:
        self.border_title = 'Search'
        self.border_subtitle = '(Enter) Search / (ESC) Close'
        self.query_one("#search-input").focus()

    def action_search(self) -> None:
        value = self.query_one("#search-input").value

        self.post_message(SearchTorrent(value))
        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)
