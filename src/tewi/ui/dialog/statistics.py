from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.app import ComposeResult
from textual.reactive import reactive

from ...util.print import print_size, print_time
from ..widget.common import ReactiveLabel


class StatisticsDialog(ModalScreen[None]):

    BINDINGS = [
            Binding("x,escape", "close", "[Info] Close"),
            ]

    def __init__(self, session_stats) -> None:
        self.session_stats = session_stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield StatisticsWidget(self.session_stats)

    def action_close(self) -> None:
        self.dismiss()


class StatisticsWidget(Static):

    r_upload = reactive("")
    r_download = reactive("")
    r_ratio = reactive("")
    r_time = reactive("")

    r_total_upload = reactive("")
    r_total_download = reactive("")
    r_total_ratio = reactive("")
    r_total_time = reactive("")
    r_total_started = reactive("")

    def __init__(self, session_stats) -> None:
        self.session_stats = session_stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("Current Session", classes="title")
        yield Static("  Uploaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_upload)
        yield Static("  Downloaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_download)
        yield Static("  Ratio:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_ratio)
        yield Static("  Running Time:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_time)
        yield Static(" ", classes="title")
        yield Static("Total", classes="title")
        yield Static("  Uploaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_upload)
        yield Static("  Downloaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_download)
        yield Static("  Ratio:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_ratio)
        yield Static("  Running Time:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_time)
        yield Static("  Started:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_started)

    def on_mount(self) -> None:
        self.border_title = 'Statistics'
        self.border_subtitle = '(X) Close'

        # current stats

        self.r_upload = print_size(self.session_stats.current_stats.uploaded_bytes)
        self.r_download = print_size(self.session_stats.current_stats.downloaded_bytes)

        self.r_ratio = self.print_ratio(self.session_stats.current_stats.uploaded_bytes,
                                        self.session_stats.current_stats.downloaded_bytes)

        self.r_time = print_time(self.session_stats.current_stats.seconds_active)

        # cumulative stats

        self.r_total_upload = print_size(self.session_stats.cumulative_stats.uploaded_bytes)
        self.r_total_download = print_size(self.session_stats.cumulative_stats.downloaded_bytes)

        self.r_total_ratio = self.print_ratio(self.session_stats.cumulative_stats.uploaded_bytes,
                                              self.session_stats.cumulative_stats.downloaded_bytes)

        self.r_total_time = print_time(self.session_stats.cumulative_stats.seconds_active)
        self.r_total_started = f"{self.session_stats.cumulative_stats.session_count} times"

    def print_ratio(self, uploaded, downloaded) -> str:
        if downloaded == 0:
            return "∞"

        ratio = uploaded / downloaded

        return f"{ratio:.2f}"
