"""Web search results panel for public torrent trackers."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from ...search.models import SearchResult
from ...search.sorting import get_search_sort_option, sort_search_results
from ...util.log import log_time
from ..dialog.search.details import TorrentDetailsDialog
from ..dialog.search.sort import SearchSortDialog
from ..messages import (
    AddTorrentFromWebSearchCommand,
    Notification,
    OpenTorrentListCommand,
)
from ..util import (
    escape_markup,
    print_size,
    subtitle_keys,
)
from ..util import (
    open as open_path,
)
from ..widget.common import ReactiveLabel


class TorrentWebSearch(Static):
    """Web search results panel for public trackers."""

    BORDER_TITLE = "Search Results"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "add_torrent", "[Action] Add Torrent"),
        Binding("o", "open_link", "[Action] Open Link"),
        Binding("enter", "show_details", "[Action] Show Details"),
        Binding("v", "toggle_view_mode", "[Action] Toggle View Mode"),
        Binding("s", "sort_results", "[Search] Sort results"),
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

    def __init__(
        self,
        hide_zero_seeders: bool,
        default_mode: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self.providers = self.app.search.get_providers()

        self._hide_zero_seeders = hide_zero_seeders
        self._view_compact = default_mode == "compact"
        self._sort_key = "seeders"
        self._sort_ascending = False
        self._display_results: list[SearchResult] = []

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
            ("V", "Toggle View"),
            ("S", "Sort"),
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
    def draw_table(self, results: list[SearchResult]) -> None:
        """Update the table when results change."""
        table = self.query_one("#websearch-results", DataTable)
        prev_cursor_row = table.cursor_row
        previous_result = self.selected_result()

        # Re-create columns after each search to force them to fit to the new
        # content. See: https://github.com/Textualize/textual/issues/6247
        table.clear(columns=True)
        self.create_table_columns()

        total_count = len(results)

        # Filter out zero-seeder results if requested
        if self._hide_zero_seeders:
            results = [r for r in results if r.seeders is None or r.seeders > 0]

        self._display_results = sort_search_results(
            results,
            self._sort_key,
            self._sort_ascending,
            compact=self._view_compact,
        )

        filtered_count = total_count - len(results)

        if filtered_count:
            detail = (
                f" ({len(results)} shown,"
                + f" {filtered_count} without seeders hidden)"
            )
        else:
            detail = ""

        if not self._display_results:
            self.r_search_status = f"No results found{detail}"
            return
        else:
            direction = "↑" if self._sort_ascending else "↓"
            sort_name = get_search_sort_option(self._sort_key).name
            self.r_search_status = (
                f"Found {total_count} results{detail}"
                f" · Sort: {sort_name} {direction}"
            )

        for r in self._display_results:
            if r.upload_date:
                if self._view_compact:
                    up_date = r.upload_date.strftime("%Y-%m")
                else:
                    up_date = r.upload_date.strftime("%Y-%m-%d")
            else:
                up_date = "-"

            # Display category full_name (first category if multiple)
            category_display = (
                r.categories[0].full_name if r.categories else "-"
            )

            title = escape_markup(r.title)
            if r.freeleech:
                title = f"[bold {self.color_success}]\\[F][/] {title}"

            if self._view_compact:
                table.add_row(
                    r.provider_short or r.provider,
                    up_date,
                    r.seeders,
                    print_size(r.size, ndigits=0),
                    category_display,
                    title,
                    key=r.info_hash,
                )
            else:
                table.add_row(
                    r.provider,
                    up_date,
                    r.seeders,
                    r.leechers,
                    r.downloads if r.downloads is not None else "-",
                    print_size(r.size),
                    r.files_count if r.files_count is not None else "-",
                    category_display,
                    title,
                    key=r.info_hash,
                )

        table.focus()

        # Preserve the selected torrent when the view mode or sort changes.
        selected_row = next(
            (
                i
                for i, result in enumerate(self._display_results)
                if result is previous_result
            ),
            min(prev_cursor_row or 0, len(self._display_results) - 1),
        )
        table.move_cursor(row=selected_row)

    @log_time
    def watch_r_results(self, results: list[SearchResult]) -> None:
        self.draw_table(results)

    @log_time
    def create_table_columns(self) -> None:
        table = self.query_one("#websearch-results", DataTable)

        def add_column(label: str, key: str) -> None:
            if key == self._sort_key:
                label += " ↑" if self._sort_ascending else " ↓"
            table.add_column(label, key=key)

        add_column("Source", "source")
        add_column("Uploaded", "uploaded")
        add_column("S", "seeders")
        if not self._view_compact:
            add_column("L", "leechers")
            add_column("D", "downloads")
        add_column("Size", "size")
        if not self._view_compact:
            add_column("Files", "files")
        add_column("Category", "category")
        add_column("Name", "name")

    # Actions

    @log_time
    def action_close(self) -> None:
        """Return to main torrent list."""
        self.post_message(OpenTorrentListCommand())

    @log_time
    def action_sort_results(self) -> None:
        self.app.push_screen(SearchSortDialog(), self.update_sort_order)

    @log_time
    def update_sort_order(self, selection: tuple[str, bool] | None) -> None:
        if selection is None:
            return
        self._sort_key, self._sort_ascending = selection
        self.draw_table(self.r_results)

    def selected_result(self) -> SearchResult | None:
        """Return the result at the visible cursor position."""
        row = self.query_one("#websearch-results", DataTable).cursor_row
        if row is None or row < 0 or row >= len(self._display_results):
            return None
        return self._display_results[row]

    @log_time
    def action_show_details(self) -> None:
        """Show detailed information for the selected torrent."""
        result = self.selected_result()
        if result is None:
            self.post_message(Notification("No torrent selected", "warning"))
            return

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
        result = self.selected_result()
        if result is None:
            self.post_message(Notification("No torrent selected", "warning"))
            return

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
        result = self.selected_result()
        if result is None:
            self.post_message(Notification("No torrent selected", "warning"))
            return

        if result.page_url:
            open_path(result.page_url)

    @log_time
    def action_toggle_view_mode(self) -> None:
        """Toggle between standard and compact view modes."""
        self._view_compact = not self._view_compact
        self.draw_table(self.r_results)

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
        self.r_results = []
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
