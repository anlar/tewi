from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Label
from textual.app import ComposeResult
from ...service.client import ClientStats
from ...util.print import print_size, print_time, print_ratio


class StatisticsDialog(ModalScreen[None]):

    BINDINGS = [
            Binding("x,escape", "close", "[Info] Close"),
            ]

    def __init__(self, stats: ClientStats) -> None:
        self.stats = stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield StatisticsWidget(self.stats)

    def action_close(self) -> None:
        self.dismiss()


class StatisticsWidget(Static):

    def __init__(self, stats: ClientStats) -> None:
        self.stats = stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("Current Session", classes="title")
        yield Static("  Uploaded:")
        yield Label(print_size(self.stats['current_uploaded_bytes']))
        yield Static("  Downloaded:")
        yield Label(print_size(self.stats['current_downloaded_bytes']))
        yield Static("  Ratio:")
        yield Label(print_ratio(self.stats['current_ratio']))
        yield Static("  Running Time:")
        yield Label(print_time(self.stats['current_active_seconds']))
        yield Static(" ", classes="title")
        yield Static("Total", classes="title")
        yield Static("  Uploaded:")
        yield Label(print_size(self.stats['total_uploaded_bytes']))
        yield Static("  Downloaded:")
        yield Label(print_size(self.stats['total_downloaded_bytes']))
        yield Static("  Ratio:")
        yield Label(print_ratio(self.stats['total_ratio']))
        yield Static("  Running Time:")
        yield Label(print_time(self.stats['total_active_seconds']))
        yield Static("  Started:")
        yield Label(f"{self.stats['total_started_count']} times")

    def on_mount(self) -> None:
        self.border_title = 'Statistics'
        self.border_subtitle = '(X) Close'
