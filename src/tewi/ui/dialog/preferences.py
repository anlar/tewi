from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, DataTable
from textual.app import ComposeResult


class PreferencesDialog(ModalScreen[None]):

    BINDINGS = [
            Binding("k", "scroll_up", "[Navigation] Scroll up"),
            Binding("j", "scroll_down", "[Navigation] Scroll down"),

            Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
            Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),

            Binding("x,escape", "close", "[Navigation] Close"),
            ]

    def __init__(self, preferences):
        self.preferences = preferences
        super().__init__()

    def compose(self) -> ComposeResult:
        yield PreferencesWidget(self.preferences)

    def action_scroll_up(self) -> None:
        self.query_one(DataTable).scroll_up()

    def action_scroll_down(self) -> None:
        self.query_one(DataTable).scroll_down()

    def action_scroll_top(self) -> None:
        self.query_one(DataTable).scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one(DataTable).scroll_end()

    def action_close(self) -> None:
        self.dismiss(False)


class PreferencesWidget(Static):

    def __init__(self, preferences):
        self.preferences = preferences
        super().__init__()

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none",
                        zebra_stripes=True)

    def on_mount(self) -> None:
        self.border_title = 'Transmission Preferences'
        self.border_subtitle = '(X) Close'

        table = self.query_one(DataTable)
        table.add_columns("Name", "Value")

        for key in self.preferences:
            table.add_row(key, self.preferences[key])
