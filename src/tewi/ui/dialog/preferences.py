from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ...util.log import log_time
from ..util import subtitle_keys


class PreferencesDialog(ModalScreen[None]):
    BINDINGS = [
        Binding("k", "scroll_up", "[Navigation] Scroll up"),
        Binding("j", "scroll_down", "[Navigation] Scroll down"),
        Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
        Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),
        Binding("x,escape", "close", "[Navigation] Close"),
    ]

    @log_time
    def __init__(self, preferences):
        self.preferences = preferences
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield PreferencesWidget(self.preferences)

    @log_time
    def action_scroll_up(self) -> None:
        self.query_one(DataTable).scroll_up()

    @log_time
    def action_scroll_down(self) -> None:
        self.query_one(DataTable).scroll_down()

    @log_time
    def action_scroll_top(self) -> None:
        self.query_one(DataTable).scroll_home()

    @log_time
    def action_scroll_bottom(self) -> None:
        self.query_one(DataTable).scroll_end()

    @log_time
    def action_close(self) -> None:
        self.dismiss(False)


class PreferencesWidget(Static):
    @log_time
    def __init__(self, preferences):
        self.preferences = preferences
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none", zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Torrent Client Preferences"
        self.border_subtitle = subtitle_keys(("X", "Close"))

        table = self.query_one(DataTable)
        table.add_columns("Name", "Value")

        for key in self.preferences:
            table.add_row(key, self.preferences[key])
