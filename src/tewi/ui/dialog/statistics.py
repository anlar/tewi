from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from ...torrent.models import ClientStats
from ...util.log import log_time
from ..util import print_ratio, print_size, print_time, subtitle_keys


class StatisticsDialog(ModalScreen[None]):
    BINDINGS = [
        Binding("x,escape", "close", "[Info] Close"),
    ]

    @log_time
    def __init__(self, stats: ClientStats) -> None:
        self.stats = stats
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield StatisticsWidget(self.stats)

    @log_time
    def action_close(self) -> None:
        self.dismiss()


class StatisticsWidget(Static):
    @log_time
    def __init__(self, stats: ClientStats) -> None:
        self.stats = stats
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield from self._compose_current_session()
        yield from self._compose_total()
        yield from self._compose_cache_stats()
        yield from self._compose_performance_stats()

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Statistics"
        self.border_subtitle = subtitle_keys(("X", "Close"))

    def _compose_current_session(self) -> ComposeResult:
        yield Static("Current Session", classes="title")
        yield Static("  Uploaded:")
        yield Label(
            "-"
            if self.stats["current_uploaded_bytes"] is None
            else print_size(self.stats["current_uploaded_bytes"])
        )
        yield Static("  Downloaded:")
        yield Label(
            "-"
            if self.stats["current_downloaded_bytes"] is None
            else print_size(self.stats["current_downloaded_bytes"])
        )
        yield Static("  Ratio:")
        yield Label(
            "-"
            if self.stats["current_ratio"] is None
            else print_ratio(self.stats["current_ratio"])
        )
        if self.stats["current_active_seconds"] is not None:
            yield Static("  Running Time:")
            yield Label(print_time(self.stats["current_active_seconds"]))
        if self.stats["current_waste"] is not None:
            yield Static("  Waste:")
            yield Label(print_size(self.stats["current_waste"]))
        if self.stats["current_connected_peers"] is not None:
            yield Static("  Connected Peers:")
            yield Label(str(self.stats["current_connected_peers"]))

    def _compose_total(self) -> ComposeResult:
        if (
            self.stats["total_uploaded_bytes"] is not None
            or self.stats["total_downloaded_bytes"] is not None
            or self.stats["total_ratio"] is not None
            or self.stats["total_active_seconds"] is not None
            or self.stats["total_started_count"] is not None
        ):
            yield Static(" ", classes="title")
            yield Static("Total", classes="title")
            yield Static("  Uploaded:")
            yield Label(
                "-"
                if self.stats["total_uploaded_bytes"] is None
                else print_size(self.stats["total_uploaded_bytes"])
            )
            yield Static("  Downloaded:")
            yield Label(
                "-"
                if self.stats["total_downloaded_bytes"] is None
                else print_size(self.stats["total_downloaded_bytes"])
            )
            yield Static("  Ratio:")
            yield Label(
                "-"
                if self.stats["total_ratio"] is None
                else print_ratio(self.stats["total_ratio"])
            )
            if self.stats["total_active_seconds"] is not None:
                yield Static("  Running Time:")
                yield Label(print_time(self.stats["total_active_seconds"]))
            if self.stats["total_started_count"] is not None:
                yield Static("  Started:")
                yield Label(f"{self.stats['total_started_count']} times")

    def _compose_cache_stats(self) -> ComposeResult:
        """Render Cache statistics block (qBittorrent only)."""
        if (
            self.stats["cache_read_hits"] is not None
            or self.stats["cache_total_buffers_size"] is not None
        ):
            yield Static(" ", classes="title")
            yield Static("Cache", classes="title")
            if self.stats["cache_read_hits"] is not None:
                yield Static("  Read Cache Hits:")
                yield Label(f"{self.stats['cache_read_hits']:.1f}%")
            if self.stats["cache_total_buffers_size"] is not None:
                yield Static("  Total Buffer Size:")
                yield Label(print_size(self.stats["cache_total_buffers_size"]))

    def _compose_performance_stats(self) -> ComposeResult:
        """Render Performance statistics block (qBittorrent only)."""
        if (
            self.stats["perf_write_cache_overload"] is not None
            or self.stats["perf_read_cache_overload"] is not None
            or self.stats["perf_queued_io_jobs"] is not None
            or self.stats["perf_average_time_queue"] is not None
            or self.stats["perf_total_queued_size"] is not None
        ):
            yield Static(" ", classes="title")
            yield Static("Performance", classes="title")
            if self.stats["perf_write_cache_overload"] is not None:
                yield Static("  Write Cache Overload:")
                yield Label(str(self.stats["perf_write_cache_overload"]))
            if self.stats["perf_read_cache_overload"] is not None:
                yield Static("  Read Cache Overload:")
                yield Label(str(self.stats["perf_read_cache_overload"]))
            if self.stats["perf_queued_io_jobs"] is not None:
                yield Static("  Queued I/O Jobs:")
                yield Label(str(self.stats["perf_queued_io_jobs"]))
            if self.stats["perf_average_time_queue"] is not None:
                yield Static("  Average Time in Queue:")
                yield Label(print_time(self.stats["perf_average_time_queue"]))
            if self.stats["perf_total_queued_size"] is not None:
                yield Static("  Total Queued Size:")
                yield Label(print_size(self.stats["perf_total_queued_size"]))
