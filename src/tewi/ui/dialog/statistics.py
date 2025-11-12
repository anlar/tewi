from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Label
from textual.app import ComposeResult
from ...service import ClientStats
from ...util.print import print_size, print_time, print_ratio
from ...util.decorator import log_time


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
        yield Static("Current Session", classes="title")
        yield Static("  Uploaded:")
        yield Label("N/A" if self.stats['current_uploaded_bytes'] is None
                    else print_size(self.stats['current_uploaded_bytes']))
        yield Static("  Downloaded:")
        yield Label("N/A" if self.stats['current_downloaded_bytes'] is None
                    else print_size(self.stats['current_downloaded_bytes']))
        yield Static("  Ratio:")
        yield Label("N/A" if self.stats['current_ratio'] is None
                    else print_ratio(self.stats['current_ratio']))
        yield Static("  Running Time:")
        yield Label("N/A" if self.stats['current_active_seconds'] is None
                    else print_time(self.stats['current_active_seconds']))
        yield Static(" ", classes="title")
        yield Static("Total", classes="title")
        yield Static("  Uploaded:")
        yield Label("N/A" if self.stats['total_uploaded_bytes'] is None
                    else print_size(self.stats['total_uploaded_bytes']))
        yield Static("  Downloaded:")
        yield Label("N/A" if self.stats['total_downloaded_bytes'] is None
                    else print_size(self.stats['total_downloaded_bytes']))
        yield Static("  Ratio:")
        yield Label("N/A" if self.stats['total_ratio'] is None
                    else print_ratio(self.stats['total_ratio']))
        yield Static("  Running Time:")
        yield Label("N/A" if self.stats['total_active_seconds'] is None
                    else print_time(self.stats['total_active_seconds']))
        yield Static("  Started:")
        yield Label("N/A" if self.stats['total_started_count'] is None
                    else f"{self.stats['total_started_count']} times")

    @log_time
    def on_mount(self) -> None:
        self.border_title = 'Statistics'
        self.border_subtitle = '(X) Close'
