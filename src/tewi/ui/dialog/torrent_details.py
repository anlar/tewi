"""Torrent details dialog for web search results."""

import webbrowser

from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Markdown
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer

from ...util.decorator import log_time
from ...message import AddTorrentFromWebSearchCommand, Notification


class TorrentDetailsDialog(ModalScreen[None]):
    """Modal dialog for displaying torrent details in markdown format."""

    BINDINGS = [
        Binding("a", "add_torrent", "[Action] Add Torrent"),
        Binding("o", "open_link", "[Action] Open Link"),

        Binding("x,escape", "close", "[Navigation] Close"),

        Binding("k,up", "scroll_up", "[Navigation] Scroll up"),
        Binding("j,down", "scroll_down", "[Navigation] Scroll down"),

        Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
        Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),
    ]

    @log_time
    def __init__(self, title: str, common_content: str,
                 extended_content: str,
                 site_link: str | None = None,
                 magnet_link: str | None = None,
                 torrent_link: str | None = None) -> None:
        """Initialize the dialog with torrent details.

        Args:
            title: Torrent title
            common_content: Common details (left column)
            extended_content: Provider-specific details (right column)
            magnet_link: Optional magnet link for adding torrent
            torrent_link: Optional torrent link for adding torrent
        """
        super().__init__()
        self.title = title
        self.common_content = common_content
        self.extended_content = extended_content
        self.site_link = site_link
        self.magnet_link = magnet_link
        self.torrent_link = torrent_link

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        yield TorrentDetailsWidget(self.title, self.common_content,
                                   self.extended_content)

    @log_time
    def action_scroll_up(self) -> None:
        self.query_one(ScrollableContainer).scroll_up()

    @log_time
    def action_scroll_down(self) -> None:
        self.query_one(ScrollableContainer).scroll_down()

    @log_time
    def action_scroll_top(self) -> None:
        self.query_one(ScrollableContainer).scroll_home()

    @log_time
    def action_scroll_bottom(self) -> None:
        self.query_one(ScrollableContainer).scroll_end()

    @log_time
    def action_add_torrent(self) -> None:
        """Add the torrent to the client."""
        if self.magnet_link:
            self.post_message(AddTorrentFromWebSearchCommand(self.magnet_link))
            self.dismiss()
        elif self.torrent_link:
            self.post_message(AddTorrentFromWebSearchCommand(self.torrent_link))
            self.dismiss()
        else:
            self.post_message(Notification(
                "No magnet/torrent link available for this torrent",
                "warning"))

    @log_time
    def action_open_link(self) -> None:
        if self.site_link:
            webbrowser.open(self.site_link)

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
        with ScrollableContainer():
            with Horizontal(classes='details-block'):
                yield Markdown(self.common_content, classes="details-column")
                yield Markdown(self.extended_content, classes="details-column")

    @log_time
    def on_mount(self) -> None:
        """Set border title and subtitle, focus left column."""
        self.border_title = 'Torrent Details'
        self.border_subtitle = '(A) Add / (O) Open Link / (X) Close'
