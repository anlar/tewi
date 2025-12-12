from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ....util.log import log_time
from ...messages import FilterUpdatedEvent
from ...models import filter_options
from ...util import subtitle_keys


class FilterDialog(ModalScreen):
    @log_time
    def compose(self) -> ComposeResult:
        yield FilterWidget()


class FilterWidget(Static):
    BINDINGS = [
        Binding("escape,x", "close", "[Navigation] Close"),
    ]

    @log_time
    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none", zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Filter"
        self.border_subtitle = subtitle_keys(("X", "Close"))

        table = self.query_one(DataTable)
        table.add_columns("Filter", "Key")

        for f in filter_options:
            table.add_row(
                f.display_name, Text(str(f"{f.key}"), justify="center")
            )

            b = Binding(f.key, f"select_filter('{f.id}')")
            self._bindings._add_binding(b)

    @log_time
    def action_select_filter(self, filter_id):
        filter_option = next(x for x in filter_options if x.id == filter_id)

        self.post_message(FilterUpdatedEvent(filter_option))

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
