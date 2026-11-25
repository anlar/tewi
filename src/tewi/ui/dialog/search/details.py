"""Torrent details dialog for web search results."""

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Link, Static

from ....search.models import DetailsLink, DetailsSection
from ....util.log import log_time
from ....util.misc import strip_control_chars
from ...messages import AddTorrentFromWebSearchCommand, Notification
from ...util import plain_text, subtitle_keys


class TorrentDetailsDialog(ModalScreen[None]):
    """Modal dialog for displaying torrent details."""

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
    def __init__(
        self,
        title: str,
        page_url: str,
        common_sections: list[DetailsSection],
        extended_sections: list[DetailsSection],
        site_link: str | None = None,
        magnet_link: str | None = None,
        torrent_link: str | None = None,
    ) -> None:
        """Initialize the dialog with torrent details.

        Args:
            title: Torrent title
            common_sections: Common details (left column)
            extended_sections: Provider-specific details (right column)
            magnet_link: Optional magnet link for adding torrent
            torrent_link: Optional torrent link for adding torrent
        """
        super().__init__()
        self.title = title
        self.page_url = page_url
        self.common_sections = common_sections
        self.extended_sections = extended_sections
        self.site_link = site_link
        self.magnet_link = magnet_link
        self.torrent_link = torrent_link

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        yield TorrentDetailsWidget(
            self.title,
            self.page_url,
            self.common_sections,
            self.extended_sections,
        )

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
            self.post_message(
                Notification(
                    "No magnet/torrent link available for this torrent",
                    "warning",
                )
            )

    @log_time
    def action_open_link(self) -> None:
        if self.site_link:
            self.app.open_url(self.site_link)

    @log_time
    def action_close(self) -> None:
        """Close the dialog."""
        self.dismiss()


class TorrentDetailsWidget(Static):
    """Widget displaying torrent details in two-column layout."""

    @log_time
    def __init__(
        self,
        title: str,
        page_url: str,
        common_sections: list[DetailsSection],
        extended_sections: list[DetailsSection],
    ) -> None:
        """Initialize the widget with torrent details.

        Args:
            title: Torrent title
            common_sections: Common details (left column)
            extended_sections: Provider-specific details (right column)
        """
        super().__init__()
        # Not all details come from SearchResult, which strips control
        # characters (e.g. details loaded on demand), so escape sequences
        # in them would be passed to terminal
        self.title = strip_control_chars(title)
        self.page_url = strip_control_chars(page_url or "")
        self.common_sections = common_sections
        self.extended_sections = extended_sections

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the two-column layout with title (top) and link (bottom)."""
        yield Static(self.title, markup=False, classes="details-title")
        with ScrollableContainer():
            with Horizontal(classes="details-block"):
                yield DetailsColumn(self.common_sections)
                yield DetailsColumn(self.extended_sections)
        with Horizontal(classes="details-link"):
            yield Static("[bold]Link:[/]", classes="details-link-left")
            yield Link(
                self.page_url,
                url=self.page_url,
                classes="details-link-right",
            )

    @log_time
    def on_mount(self) -> None:
        """Set border title and subtitle, focus left column."""
        self.border_title = "Torrent Details"
        self.border_subtitle = subtitle_keys(
            ("A", "Add"), ("O", "Open Link"), ("X", "Close")
        )


def single_line(value: object) -> str:
    """Join lines of value and collapse whitespace, for field values."""
    return " ".join(str(value).split())


class DetailsColumn(Vertical):
    """Column of search result details sections.

    Text comes from search providers, so it's shown literally (never
    parsed as markup) and without control characters.
    """

    @log_time
    def __init__(self, sections: list[DetailsSection]) -> None:
        super().__init__(classes="details-column")
        self.sections = sections

    @log_time
    def compose(self) -> ComposeResult:
        for section in self.sections:
            if not (section.fields or section.items or section.text):
                continue

            yield Label(plain_text(section.title), classes="details-section")

            if section.fields:
                with Grid(classes="details-fields"):
                    for label, value in section.fields:
                        yield Label(
                            plain_text(f"{single_line(label)}:"),
                            classes="details-label",
                        )
                        yield self.value_widget(value)

            if section.items:
                yield Static(
                    self.items_table(section.items), classes="details-items"
                )

            if section.text:
                yield Static(plain_text(section.text), classes="details-text")

    def value_widget(self, value: str | DetailsLink) -> Static:
        """Create widget showing field value, link is opened on click."""
        if isinstance(value, DetailsLink):
            url = strip_control_chars(single_line(value.url))
            return Link(url, url=url)
        return Static(plain_text(single_line(value)))

    def items_table(self, items: list[str]) -> Table:
        """Create bulleted list, wrapped items are aligned after bullet."""
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True)
        table.add_column(overflow="fold")
        for item in items:
            table.add_row("•", plain_text(single_line(item)))
        return table
