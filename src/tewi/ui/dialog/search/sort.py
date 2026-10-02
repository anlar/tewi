"""Sort order selector for web search results."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ....search.sorting import SEARCH_SORT_OPTIONS
from ....util.log import log_time
from ...util import subtitle_keys


class SearchSortDialog(ModalScreen[tuple[str, bool] | None]):
    @log_time
    def compose(self) -> ComposeResult:
        yield SearchSortWidget()


class SearchSortWidget(Static):
    BINDINGS = [Binding("escape,x", "close", "[Navigation] Close")]

    @log_time
    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none", zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Sort search results"
        self.border_subtitle = subtitle_keys(("X", "Close"))

        table = self.query_one(DataTable)
        table.add_columns("Column", "Key (ASC | DESC)")

        for option in SEARCH_SORT_OPTIONS:
            table.add_row(
                option.name,
                Text(
                    f"   {option.hotkey} | {option.hotkey.upper()}",
                    justify="center",
                ),
            )
            for ascending, key in (
                (True, option.hotkey),
                (False, option.hotkey.upper()),
            ):
                self._bindings._add_binding(
                    Binding(key, f"select_order('{option.key}', {ascending})")
                )

    @log_time
    def action_select_order(self, key: str, ascending: bool) -> None:
        self.parent.dismiss((key, ascending))

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(None)
