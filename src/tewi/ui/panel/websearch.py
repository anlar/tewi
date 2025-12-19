"""Web search results panel for public torrent trackers."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from ...search.models import SearchResult
from ...util.log import log_time
from ..dialog.search.details import TorrentDetailsDialog
from ..messages import (
    AddTorrentFromWebSearchCommand,
    Notification,
    OpenTorrentListCommand,
)
from ..util import escape_markup, print_size, subtitle_keys
from ..widget.common import ReactiveLabel


class TorrentWebSearch(Static):
    """Web search results panel for public trackers."""

    BORDER_TITLE = "Search Results"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "add_torrent", "[Action] Add Torrent"),
        Binding("o", "open_link", "[Action] Open Link"),
        Binding("enter", "show_details", "[Action] Show Details"),
        Binding("x,escape", "close", "[Navigation] Close"),
        Binding("j,down", "cursor_down", "[Navigation] Move down"),
        Binding("k,up", "cursor_up", "[Navigation] Move up"),
        Binding("h,left", "cursor_left", "[Navigation] Move left"),
        Binding("l,right", "cursor_right", "[Navigation] Move right"),
        Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
        Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),
    ]

    r_query: str = reactive("")
    r_search_status: str = reactive(False)
    # always update to trigger focus setup and label updates
    # to cover case when search executes on the same query twice
    r_results: list[SearchResult] = reactive(list, always_update=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.providers = self.app.search.get_providers()

        # Workaround to get color from theme, because DataTable doesn't
        # support CSS variables lik $success.
        # See: https://github.com/Textualize/textual/issues/6273
        self.color_success = self.app.current_theme.success

    @log_time
    def compose(self) -> ComposeResult:
        with Vertical():
            yield ReactiveLabel(id="search-query-label").data_bind(
                name=TorrentWebSearch.r_query
            )
            yield ReactiveLabel(id="search-status").data_bind(
                name=TorrentWebSearch.r_search_status
            )
            yield DataTable(
                id="websearch-results",
                show_cursor=True,
                cursor_type="row",
                zebra_stripes=True,
            )

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Search Results"
        self.border_subtitle = subtitle_keys(
            ("A", "Add"),
            ("O", "Open Link"),
            ("Enter", "Details"),
            ("X", "Close"),
        )
        self.create_table_columns()

    @log_time
    def execute_search(
        self,
        query: str,
        selected_indexers: list[str] | None = None,
        selected_categories: list[str] | None = None,
    ) -> None:
        """Execute search with given query.

        Args:
            query: Search term
            selected_indexers: List of indexer IDs to search,
                              or None to search all
        """

        self.r_query = f"Query: {query}"

        # Start background search
        self.perform_search(query, selected_indexers, selected_categories)

    @log_time
    def watch_r_results(self, results: list[SearchResult]) -> None:
        """Update the table when results change."""
        table = self.query_one("#websearch-results", DataTable)

        # Re-create columns after each search to force them to fit to the new
        # content. See: https://github.com/Textualize/textual/issues/6247
        table.clear(columns=True)
        self.create_table_columns()

        if not results:
            self.r_search_status = "No results found"
            return
        else:
            self.r_search_status = f"Found {len(results)} results"

        for r in results:
            up_date = (
                r.upload_date.strftime("%Y-%m-%d") if r.upload_date else "-"
            )

            # Display category full_name (first category if multiple)
            category_display = (
                r.categories[0].full_name if r.categories else "-"
            )

            title = escape_markup(r.title)
            if r.freeleech:
                title = f"[bold {self.color_success}]\\[F][/] {title}"

            table.add_row(
                r.provider,
                up_date,
                r.seeders,
                r.leechers,
                r.downloads or "-",
                print_size(r.size),
                r.files_count or "-",
                category_display,
                title,
                key=r.info_hash,
            )

        table.focus()

    @log_time
    def create_table_columns(self) -> None:
        table = self.query_one("#websearch-results", DataTable)

        table.add_column("Source", key="source")
        table.add_column("Uploaded", key="uploaded")
        table.add_column("S ↓", key="seeders")
        table.add_column("L", key="leechers")
        table.add_column("D", key="downloads")
        table.add_column("Size", key="size")
        table.add_column("Files", key="files")
        table.add_column("Category", key="category")
        table.add_column("Name", key="name")

    # Actions

    @log_time
    def action_close(self) -> None:
        """Return to main torrent list."""
        self.post_message(OpenTorrentListCommand())

    @log_time
    def action_show_details(self) -> None:
        """Show detailed information for the selected torrent."""
        table = self.query_one("#websearch-results", DataTable)

        if not self.r_results:
            return

        # Get selected row
        if table.cursor_row is None or table.cursor_row < 0:
            self.post_message(Notification("No torrent selected", "warning"))
            return

        # Find the corresponding result
        if table.cursor_row >= len(self.r_results):
            return

        result = self.r_results[table.cursor_row]

        # Find the provider instance using provider_id
        provider = None
        for p in self.providers:
            if p.id == result.provider_id:
                provider = p
                break

        if not provider:
            self.post_message(
                Notification(
                    f"Provider with ID '{result.provider_id}' not found",
                    "error",
                )
            )
            return

        # Generate details using the provider
        common_content = provider.details_common(result)
        extended_content = provider.details_extended(result)

        # Show the details dialog
        self.app.push_screen(
            TorrentDetailsDialog(
                result.title,
                result.page_url,
                common_content,
                extended_content,
                result.page_url,
                result.magnet_link,
                result.torrent_link,
            )
        )

    @log_time
    def action_add_torrent(self) -> None:
        """Add the selected torrent to the client."""
        table = self.query_one("#websearch-results", DataTable)

        if not self.r_results:
            return

        # Get selected row
        if table.cursor_row is None or table.cursor_row < 0:
            self.post_message(Notification("No torrent selected", "warning"))
            return

        # Find the corresponding result
        if table.cursor_row >= len(self.r_results):
            return

        result = self.r_results[table.cursor_row]

        # Post command to add torrent
        if result.magnet_link:
            self.post_message(
                AddTorrentFromWebSearchCommand(result.magnet_link)
            )
        elif result.torrent_link:
            self.post_message(
                AddTorrentFromWebSearchCommand(result.torrent_link)
            )
        else:
            self.post_message(
                Notification(
                    "No magnet/torrent link available for this torrent",
                    "warning",
                )
            )

    @log_time
    def action_open_link(self) -> None:
        table = self.query_one("#websearch-results", DataTable)

        if not self.r_results:
            return

        # Get selected row
        if table.cursor_row is None or table.cursor_row < 0:
            self.post_message(Notification("No torrent selected", "warning"))
            return

        # Find the corresponding result
        if table.cursor_row >= len(self.r_results):
            return

        result = self.r_results[table.cursor_row]

        if result.page_url:
            self.app.open_url(result.page_url)

    @log_time
    def action_cursor_down(self) -> None:
        """Move cursor down in table."""
        table = self.query_one("#websearch-results", DataTable)
        table.action_cursor_down()

    @log_time
    def action_cursor_up(self) -> None:
        """Move cursor up in table."""
        table = self.query_one("#websearch-results", DataTable)
        table.action_cursor_up()

    @log_time
    def action_cursor_left(self) -> None:
        """Move cursor left in table."""
        table = self.query_one("#websearch-results", DataTable)
        table.action_cursor_left()

    @log_time
    def action_cursor_right(self) -> None:
        """Move cursor right in table."""
        table = self.query_one("#websearch-results", DataTable)
        table.action_cursor_right()

    @log_time
    def action_scroll_top(self):
        self.query_one("#websearch-results").action_scroll_top()

    @log_time
    def action_scroll_bottom(self):
        self.query_one("#websearch-results").action_scroll_bottom()

    # Background search

    @log_time
    @work(exclusive=True, thread=True)
    async def perform_search(
        self,
        query: str,
        selected_indexers: list[str] | None = None,
        selected_categories: list[str] | None = None,
    ) -> None:
        """Perform search in background thread using selected providers.

        Args:
            query: Search term
            selected_indexers: List of indexer IDs to search,
                              or None to search all
        """
        self.r_search_status = "Searching..."

        all_results, errors = self.app.search.search(
            query, selected_indexers, selected_categories
        )

        self.app.call_from_thread(self.update_results, all_results, errors)

    @log_time
    def update_results(
        self, results: list[SearchResult], errors: list[str] | None
    ) -> None:
        """Update results in main thread.

        Args:
            results: Search results
            errors: Error message if search providers failed
        """

        if errors:
            for error in errors:
                self.post_message(
                    Notification(f"Search provider failed: {error}", "warning")
                )

        self.r_results = results

    # Event handlers

    @log_time
    @on(DataTable.RowSelected, "#websearch-results")
    def handle_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter on table)."""
        self.action_show_details()
