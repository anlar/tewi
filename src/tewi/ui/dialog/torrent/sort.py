from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, DataTable
from textual.app import ComposeResult

from rich.text import Text

from ....message import SortOrderSelected
from ....common import sort_orders


class SortOrderDialog(ModalScreen):

    def compose(self) -> ComposeResult:
        yield SortOrderWidget()


class SortOrderWidget(Static):

    BINDINGS = [
            Binding("escape,x", "close", "[Navigation] Close"),
            ]

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none",
                        zebra_stripes=True)

    def on_mount(self) -> None:
        self.border_title = 'Sort order'
        self.border_subtitle = '(X) Close'

        table = self.query_one(DataTable)
        table.add_columns("Order", "Key (ASC | DESC)")

        for o in sort_orders:
            table.add_row(o.name,
                          Text(str(f'   {o.key_asc} | {o.key_desc}'), justify="center"))

            b = Binding(o.key_asc, f"select_order('{o.id}', True)")
            self._bindings._add_binding(b)

            b = Binding(o.key_desc, f"select_order('{o.id}', False)")
            self._bindings._add_binding(b)

    def action_select_order(self, sort_id, is_asc):
        order = next(x for x in sort_orders if x.id == sort_id)

        self.post_message(SortOrderSelected(order, is_asc))

        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)
