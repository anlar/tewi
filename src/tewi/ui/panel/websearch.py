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
from ...common import SearchResultDTO
from ...message import (
    OpenTorrentListCommand,
    AddTorrentFromWebSearchCommand,
    Notification
)
from ...service.search import YTSProvider, TorrentsCsvProvider, \
    TPBProvider, NyaaProvider
from ...util.decorator import log_time
from ...util.print import print_size


class TorrentWebSearch(Static):
    """Web search results panel for public trackers."""

    BORDER_TITLE = "Search Results"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,h,left", "close", "[Navigation] Close"),
        Binding("enter,l,right", "add_torrent", "[Action] Add Torrent"),
        Binding("j,down", "cursor_down", "[Navigation] Move down"),
        Binding("k,up", "cursor_up", "[Navigation] Move up"),
        Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
        Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),
    ]

    r_query: str = reactive("")
    r_search_status: str = reactive(False)
    # always update to trigger focus setup and label updates
    # to cover case when search executes on the same query twice
    r_results: list[SearchResultDTO] = reactive(list, always_update=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.providers = [YTSProvider(), TorrentsCsvProvider(),
                          TPBProvider(), NyaaProvider()]

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
        table = self.query_one("#websearch-results", DataTable)

        table.add_column("Source", key="source")
        table.add_column("Uploaded", key="uploaded")
        table.add_column("S ↓", key="seeders")
        table.add_column("L", key="leechers")
        table.add_column("Size", key="size")
        table.add_column("Files", key="files")
        table.add_column("Category", key="category")
        table.add_column("Name", key="name")

    @log_time
    def execute_search(self, query: str) -> None:
        """Execute search with given query.

        Args:
            query: Search term
        """

        self.r_query = f"Query: {query}"

        # Start background search
        self.perform_search(query)

    @log_time
    def watch_r_results(self, results: list[SearchResultDTO]) -> None:
        """Update the table when results change."""
        table = self.query_one("#websearch-results", DataTable)

        table.clear()

        if not results:
            self.r_search_status = "No results found"
            return
        else:
            self.r_search_status = f"Found {len(results)} results"

        for r in results:
            up_date = r.upload_date.strftime("%Y-%m-%d") if r.upload_date else '-'

            table.add_row(
                r.provider,
                up_date,
                r.seeders,
                r.leechers,
                print_size(r.size),
                r.files_count or '-',
                r.category or '-',
                r.title,
                key=r.info_hash
            )

        table.focus()

    # Actions

    @log_time
    def action_close(self) -> None:
        """Return to main torrent list."""
        self.post_message(OpenTorrentListCommand())

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
        self.post_message(AddTorrentFromWebSearchCommand(result.magnet_link))

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
    def action_scroll_top(self):
        self.query_one("#websearch-results").action_scroll_top()

    @log_time
    def action_scroll_bottom(self):
        self.query_one("#websearch-results").action_scroll_bottom()

    # Background search

    @log_time
    @work(exclusive=True, thread=True)
    async def perform_search(self, query: str) -> None:
        """Perform search in background thread using all providers in parallel.

        Args:
            query: Search term
        """
        self.r_search_status = "Searching..."

        all_results = []
        errors = []

        # Execute all provider searches in parallel
        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            # Submit all search tasks
            future_to_provider = {
                executor.submit(provider.search, query): provider
                for provider in self.providers
            }

            # Collect results as they complete
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    provider_results = future.result()
                    all_results.extend(provider_results)
                except Exception as e:
                    # Log error but continue with other providers
                    errors.append(f"{provider.display_name}: {str(e)}")

        # Deduplicate by info_hash, keeping result with highest seeders
        best_results = {}
        for result in all_results:
            hash_key = result.info_hash
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
        self.action_add_torrent()
