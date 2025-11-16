"""Web search query input dialog."""

from textual.binding import Binding, BindingType
from textual.widgets import Input, Static
from textual.app import ComposeResult
from textual.screen import ModalScreen
from typing import ClassVar

from ...message import WebSearchQuerySubmitted, Notification
from ...util.decorator import log_time


class WebSearchQueryDialog(ModalScreen[None]):
    """Modal dialog for entering web search query."""

    @log_time
    def compose(self) -> ComposeResult:
        yield WebSearchQueryWidget()


class WebSearchQueryWidget(Static):
    """Input widget for web search query."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "submit_query", "[Action] Search", priority=True),
        Binding("escape", "close", "[Navigation] Cancel"),
    ]

    @log_time
    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="Search for torrents...",
            id="websearch-query-input"
        )

    @log_time
    def on_mount(self) -> None:
        """Focus on input when dialog opens."""
        self.border_title = 'Search torrents'
        self.border_subtitle = '(Enter) Search / (ESC) Close'

        input_widget = self.query_one("#websearch-query-input", Input)
        input_widget.focus()

    @log_time
    def action_submit_query(self) -> None:
        """Submit search query and close dialog."""
        input_widget = self.query_one("#websearch-query-input", Input)
        query = input_widget.value.strip()

        if not query:
            self.post_message(Notification(
                "Please enter a search term",
                "warning"))
            return

        # Post message with query
        self.post_message(WebSearchQuerySubmitted(query))

        # Close dialog
        self.parent.dismiss()

    @log_time
    def action_close(self) -> None:
        """Close dialog without searching."""
        self.parent.dismiss()
