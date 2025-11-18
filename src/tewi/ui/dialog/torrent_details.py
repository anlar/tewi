"""Torrent details dialog for web search results."""

from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Markdown
from textual.app import ComposeResult
from textual.containers import Horizontal

from ...util.decorator import log_time


class TorrentDetailsDialog(ModalScreen[None]):
    """Modal dialog for displaying torrent details in markdown format."""

    BINDINGS = [
        Binding("x,escape", "close", "[Navigation] Close"),
    ]

    @log_time
    def __init__(self, title: str, common_content: str,
                 extended_content: str) -> None:
        """Initialize the dialog with torrent details.

        Args:
            title: Torrent title
            common_content: Common details (left column)
            extended_content: Provider-specific details (right column)
        """
        super().__init__()
        self.title = title
        self.common_content = common_content
        self.extended_content = extended_content

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        yield TorrentDetailsWidget(self.title, self.common_content,
                                   self.extended_content)

    @log_time
    def action_close(self) -> None:
        """Close the dialog."""
        self.dismiss()


class TorrentDetailsWidget(Static):
    """Widget displaying torrent details in two-column layout."""

    @log_time
    def __init__(self, title: str, common_content: str,
                 extended_content: str) -> None:
        """Initialize the widget with torrent details.

        Args:
            title: Torrent title
            common_content: Common details (left column)
            extended_content: Provider-specific details (right column)
        """
        super().__init__()
        self.title = title
        self.common_content = common_content
        self.extended_content = extended_content

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the two-column layout with title."""
        yield Static(self.title, classes="details-title")
        with Horizontal():
            yield Markdown(self.common_content, classes="details-column")
            yield Markdown(self.extended_content, classes="details-column")

    @log_time
    def on_mount(self) -> None:
        """Set border title and subtitle, focus left column."""
        self.border_title = 'Torrent Details'
        self.border_subtitle = '(X) Close'
