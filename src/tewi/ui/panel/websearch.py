"""Web search results panel for public torrent trackers."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import ClassVar

from textual import on, work
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Static
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive

from ..widget.common import ReactiveLabel
from ..dialog.torrent_details import TorrentDetailsDialog
from ...common import SearchResultDTO
from ...message import (
    OpenTorrentListCommand,
    AddTorrentFromWebSearchCommand,
    Notification
)
from ...service.search import (YTSProvider, TorrentsCsvProvider,
                               TPBProvider, NyaaProvider,
                               JackettProvider)
from ...util.decorator import log_time
from ...util.print import print_size


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
    r_results: list[SearchResultDTO] = reactive(list, always_update=True)

    def __init__(self,
                 jackett_url: str | None = None,
                 jackett_api_key: str | None = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.providers = [YTSProvider(),
                          TorrentsCsvProvider(),
                          TPBProvider(),
                          NyaaProvider(),
                          JackettProvider(jackett_url, jackett_api_key)]

    @log_time
    def compose(self) -> ComposeResult:
        with Vertical():
            yield ReactiveLabel(id="search-query-label").data_bind(
                    name=TorrentWebSearch.r_query)
            yield ReactiveLabel(id="search-status").data_bind(
                    name=TorrentWebSearch.r_search_status)
            yield DataTable(id="websearch-results",
                            show_cursor=True,
                            cursor_type="row",
                            zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Search Results"
        self.border_subtitle = ("(A) Add / "
                                "(O) Open Link / "
                                "(Enter) Details / "
                                "(X) Close")
        self.create_table_columns()

    @log_time
    def execute_search(self, query: str,
                       selected_indexers: list[str] | None = None) -> None:
        """Execute search with given query.

        Args:
            query: Search term
            selected_indexers: List of indexer IDs to search,
                              or None to search all
        """

        self.r_query = f"Query: {query}"

        # Start background search
        self.perform_search(query, selected_indexers)

    @log_time
    def watch_r_results(self, results: list[SearchResultDTO]) -> None:
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
            up_date = r.upload_date.strftime("%Y-%m-%d") \
                if r.upload_date else '-'

            table.add_row(
                r.provider,
                up_date,
                r.seeders,
                r.leechers,
                print_size(r.size),
                r.files_count or '-',
                r.category.value,
                r.title,
                key=r.info_hash
            )

        table.focus()

    @log_time
    def create_table_columns(self) -> None:
        table = self.query_one("#websearch-results", DataTable)

        table.add_column("Source", key="source")
        table.add_column("Uploaded", key="uploaded")
        table.add_column("S ↓", key="seeders")
        table.add_column("L", key="leechers")
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
            self.post_message(Notification(
                "No torrent selected",
                "warning"))
            return

        # Find the corresponding result
        if table.cursor_row >= len(self.r_results):
            return

        result = self.r_results[table.cursor_row]

        # Find the provider instance using provider_id
        provider = None
        for p in self.providers:
            if p.id() == result.provider_id:
                provider = p
                break

        if not provider:
            self.post_message(Notification(
                f"Provider with ID '{result.provider_id}' not found",
                "error"))
            return

        # Generate details using the provider
        common_content = provider.details_common(result)
        extended_content = provider.details_extended(result)

        # Show the details dialog
        self.app.push_screen(TorrentDetailsDialog(
            result.title, common_content, extended_content,
            result.page_url, result.magnet_link, result.torrent_link))

    @log_time
    def action_add_torrent(self) -> None:
        """Add the selected torrent to the client."""
        table = self.query_one("#websearch-results", DataTable)

        if not self.r_results:
            return

        # Get selected row
        if table.cursor_row is None or table.cursor_row < 0:
            self.post_message(Notification(
                "No torrent selected",
                "warning"))
            return

        # Find the corresponding result
        if table.cursor_row >= len(self.r_results):
            return

        result = self.r_results[table.cursor_row]

        # Post command to add torrent
        if result.magnet_link:
            self.post_message(AddTorrentFromWebSearchCommand(result.magnet_link))
        elif result.torrent_link:
            self.post_message(AddTorrentFromWebSearchCommand(result.torrent_link))
        else:
            self.post_message(Notification(
                "No magnet/torrent link available for this torrent",
                "warning"))

    @log_time
    def action_open_link(self) -> None:
        table = self.query_one("#websearch-results", DataTable)

        if not self.r_results:
            return

        # Get selected row
        if table.cursor_row is None or table.cursor_row < 0:
            self.post_message(Notification(
                "No torrent selected",
                "warning"))
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

    def _filter_providers(
            self,
            selected_indexers: list[str] | None) -> list:
        """Filter providers based on selected indexers.

        Args:
            selected_indexers: List of indexer IDs to search,
                              or None to search all

        Returns:
            List of providers to search
        """
        if selected_indexers is None:
            # Search all providers
            return self.providers

        providers_to_search = []

        # Group selected indexers by provider
        regular_providers = set()
        jackett_indexers = []

        for indexer_id in selected_indexers:
            if indexer_id.startswith('jackett:'):
                # Extract jackett indexer ID (remove 'jackett:' prefix)
                jackett_indexers.append(indexer_id[8:])
            else:
                # Regular provider
                regular_providers.add(indexer_id)

        # Add regular providers if selected
        for provider in self.providers:
            provider_id = provider.id()
            if provider_id == 'jackett':
                # Handle Jackett separately
                if jackett_indexers:
                    # Configure Jackett with selected indexers
                    provider.set_selected_indexers(jackett_indexers)
                    providers_to_search.append(provider)
            elif provider_id in regular_providers:
                # Add regular provider
                providers_to_search.append(provider)

        return providers_to_search

    @log_time
    @work(exclusive=True, thread=True)
    async def perform_search(self, query: str,
                             selected_indexers: list[str] | None = None) -> None:
        """Perform search in background thread using selected providers.

        Args:
            query: Search term
            selected_indexers: List of indexer IDs to search,
                              or None to search all
        """
        self.r_search_status = "Searching..."

        all_results = []
        errors = []

        # Filter providers based on selected indexers
        providers_to_search = self._filter_providers(selected_indexers)

        # Execute all provider searches in parallel
        with ThreadPoolExecutor(
                max_workers=len(providers_to_search)) as executor:
            # Submit all search tasks
            future_to_provider = {
                executor.submit(provider.search, query): provider
                for provider in providers_to_search
            }

            # Collect results as they complete
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    provider_results = future.result()
                    all_results.extend(provider_results)
                except Exception as e:
                    # Log error but continue with other providers
                    errors.append(f"{provider.short_name}: {str(e)}")

        # Deduplicate by info_hash, keeping result with highest seeders
        best_results = {}
        for result in all_results:
            # Use info_hash as key; fall back to title:size for results without
            if result.info_hash:
                hash_key = result.info_hash
            else:
                # Deduplicate by title + size when hash unavailable
                hash_key = f"__no_hash__{result.title}:{result.size}"

            if hash_key not in best_results:
                best_results[hash_key] = result
            else:
                # Keep the result with more seeders
                if result.seeders > best_results[hash_key].seeders:
                    best_results[hash_key] = result

        # Convert back to list and sort by seeders for relevance
        all_results = list(best_results.values())
        all_results.sort(key=lambda r: r.seeders, reverse=True)

        self.app.call_from_thread(self.update_results, all_results, errors)

    @log_time
    def update_results(self, results: list[SearchResultDTO],
                       errors: list[str] | None) -> None:
        """Update results in main thread.

        Args:
            results: Search results
            errors: Error message if search providers failed
        """

        if errors:
            for error in errors:
                self.post_message(Notification(
                    f"Search provider failed: {error}",
                    "warning"))

        self.r_results = results

    # Event handlers

    @log_time
    @on(DataTable.RowSelected, "#websearch-results")
    def handle_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (Enter on table)."""
        self.action_show_details()
