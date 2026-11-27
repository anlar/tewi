# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Torrent details dialog for web search results."""

from rich.table import Table
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Link, Static
from textual.worker import get_current_worker

from ....search.base import BaseSearchProvider, details_common
from ....search.models import (
    DetailsGroup,
    DetailsLink,
    DetailsSection,
    SearchResult,
)
from ....util.log import get_logger, log_time
from ...messages import AddTorrentFromWebSearchCommand, Notification
from ...util import plain_text, source_text, subtitle_keys

logger = get_logger()


class TorrentDetailsDialog(ModalScreen[None]):
    """Modal dialog for displaying torrent details.

    Common details are shown at once, provider-specific details of every
    result source are loaded in background, as they could request
    provider site.
    """

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
        self, result: SearchResult, providers: list[BaseSearchProvider]
    ) -> None:
        """Initialize the dialog with torrent details.

        Args:
            result: Search result to show details for
            providers: Providers to load details of result sources from
        """
        super().__init__()
        self.result = result

        providers_by_id = {p.id: p for p in providers}
        loading = (DetailsSection("", text="Loading details..."),)
        # Details available without network requests are shown at once
        self.groups: list[DetailsGroup] = []
        # Sources to load in background, with their index and provider
        self.pending: list[
            tuple[int, BaseSearchProvider | None, SearchResult]
        ] = []
        for index, source in enumerate(result.all_sources):
            provider = providers_by_id.get(source.provider_id)
            group = details_group(provider, source, offline=True)
            if group is None:
                self.pending.append((index, provider, source))
                group = DetailsGroup(
                    source.provider, source.provider_source, loading
                )
            self.groups.append(group)

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        sources = self.result.all_sources
        yield TorrentDetailsWidget(
            self.result.title,
            # Sources of several Jackett indexers could share page
            list(dict.fromkeys(s.page_url for s in sources if s.page_url)),
            details_common(self.result),
            self.groups,
        )

    @log_time
    def on_mount(self) -> None:
        """Start loading details which aren't available at once."""
        for index, provider, source in self.pending:
            self.load_group(index, provider, source)

    @work(thread=True)
    @log_time
    def load_group(
        self,
        index: int,
        provider: BaseSearchProvider | None,
        source: SearchResult,
    ) -> None:
        """Load provider-specific details of result source.

        Args:
            index: Index of source in result sources
            provider: Provider which returned the source, None if not found
            source: Result of single provider
        """
        # Group is None only for offline details
        group = details_group(provider, source)

        # Dialog's workers are cancelled when it's closed
        if group is None or get_current_worker().is_cancelled:
            return
        self.app.call_from_thread(self.show_group, index, group)

    @log_time
    def show_group(self, index: int, group: DetailsGroup) -> None:
        """Show loaded details of result source, unless dialog is closed."""
        if self.is_attached:
            block_id = f"#group-{index}"
            self.query_one(block_id, DetailsGroupBlock).show_group(group)

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
        link = self.result.magnet_link or self.result.torrent_link
        if link:
            self.post_message(AddTorrentFromWebSearchCommand(link))
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
        page_url = next(
            (s.page_url for s in self.result.all_sources if s.page_url), None
        )
        if page_url:
            self.app.open_url(page_url)

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
        page_urls: list[str],
        common_sections: list[DetailsSection],
        extended_groups: list[DetailsGroup],
    ) -> None:
        """Initialize the widget with torrent details.

        Args:
            title: Torrent title
            page_urls: Torrent pages of every result source
            common_sections: Common details (left column)
            extended_groups: Provider-specific details of every source
                (right column)
        """
        super().__init__()
        self.title = title
        self.page_urls = page_urls
        self.common_sections = common_sections
        self.extended_groups = extended_groups

    @log_time
    def compose(self) -> ComposeResult:
        """Compose the two-column layout with title (top) and links
        (bottom)."""
        yield Static(self.title, markup=False, classes="details-title")
        with ScrollableContainer():
            with Horizontal(classes="details-block"):
                yield DetailsSections(
                    self.common_sections, classes="details-column"
                )
                yield DetailsGroupsColumn(self.extended_groups)
        if not self.page_urls:
            return
        with Vertical(classes="details-link") as links:
            # Textual pads title with spaces only next to border corners
            links.border_title = (
                " Links " if len(self.page_urls) > 1 else " Link "
            )
            for url in self.page_urls:
                with Horizontal(classes="details-link-item"):
                    yield Static("•", classes="details-link-bullet")
                    yield Link(url, url=url)

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


class DetailsGroupsColumn(Vertical):
    """Column of provider-specific details, block per result source.

    Groups without anything to show are skipped. Provider title is
    shown only for results with several sources.
    """

    @log_time
    def __init__(self, groups: list[DetailsGroup]) -> None:
        super().__init__(classes="details-column")
        self.groups = groups

    @log_time
    def compose(self) -> ComposeResult:
        for index, group in enumerate(self.groups):
            if not group.empty:
                yield DetailsGroupBlock(
                    group, show_title=len(self.groups) > 1, id=f"group-{index}"
                )


class DetailsGroupBlock(Vertical):
    """Provider-specific details of one result source."""

    @log_time
    def __init__(self, group: DetailsGroup, show_title: bool, id: str) -> None:
        super().__init__(classes="details-group", id=id)
        self.group = group
        self.show_title = show_title

    @log_time
    def compose(self) -> ComposeResult:
        if self.show_title:
            yield Static(
                source_text(self.group.title, self.group.source),
                classes="details-group-title",
            )
        yield DetailsSections(self.group.sections)

    @log_time
    def show_group(self, group: DetailsGroup) -> None:
        """Replace shown details, e.g. when they are loaded.

        Block is removed if group has nothing to show.
        """
        if group.empty:
            self.remove()
            return
        self.query_one(DetailsSections).remove()
        self.mount(DetailsSections(group.sections))


class DetailsSections(Vertical):
    """Search result details sections.

    Text comes from search providers, so it's shown literally (never
    parsed as markup). Control characters are removed by DTOs.
    """

    @log_time
    def __init__(
        self,
        sections: list[DetailsSection] | tuple[DetailsSection, ...],
        classes: str = "",
    ) -> None:
        super().__init__(classes=f"details-sections {classes}".strip())
        self.sections = sections

    @log_time
    def compose(self) -> ComposeResult:
        for section in self.sections:
            if section.empty:
                continue

            if section.title:
                yield Label(
                    plain_text(section.title), classes="details-section"
                )

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
            url = single_line(value.url)
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


@log_time
def details_group(
    provider: BaseSearchProvider | None,
    source: SearchResult,
    offline: bool = False,
) -> DetailsGroup | None:
    """Generate provider-specific details of one source of result.

    Failure is shown in group, so details of other sources are
    still shown.

    Args:
        provider: Provider which returned the source, None if not found
        source: Result of single provider
        offline: Generate only details available without network
            requests (see `BaseSearchProvider.details_extended_offline`)

    Returns:
        Group with provider details or error, None if offline details
        aren't available
    """
    sections: list[DetailsSection] | None
    if provider is None:
        error = f"Provider with ID '{source.provider_id}' not found"
        sections = [DetailsSection("Error", text=error)]
    else:
        try:
            if offline:
                sections = provider.details_extended_offline(source)
            else:
                sections = provider.details_extended(source)
        except Exception as e:
            logger.warning(f"Failed to load {source.provider} details: {e}")
            error = f"Failed to load details: {e}"
            sections = [DetailsSection("Error", text=error)]

    if sections is None:
        return None
    return DetailsGroup(
        source.provider, source.provider_source, tuple(sections)
    )
