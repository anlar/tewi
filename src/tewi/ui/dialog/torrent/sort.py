from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ....util.log import log_time
from ...messages import SortOrderUpdatedEvent
from ...models import SortKey, sort_orders
from ...util import subtitle_keys

# fits longest position label, e.g. "13↑"
POSITION_WIDTH = len(f"{len(sort_orders)}↑")
# fixed width, so only order names shift when position prefix is shown
ORDER_WIDTH = POSITION_WIDTH + 1 + max(len(o.name) for o in sort_orders)


class SortOrderDialog(ModalScreen):
    def __init__(self, sort_keys: tuple[SortKey, ...]) -> None:
        super().__init__()
        self.sort_keys = sort_keys

    @log_time
    def compose(self) -> ComposeResult:
        yield SortOrderWidget(self.sort_keys)


class SortOrderWidget(Static):
    """Sort order selector.

    In single mode selected order is applied and dialog closes. In multi
    mode each selected order is appended to the chain of sort keys (later
    keys break ties of earlier ones) and applied immediately.
    """

    BINDINGS = [
        Binding("m", "toggle_multi", "[Sort] Toggle multiple"),
        Binding("escape,x", "close", "[Navigation] Close"),
    ]

    def __init__(self, sort_keys: tuple[SortKey, ...]) -> None:
        super().__init__()
        # reopen in multi mode to show existing chain of sort keys
        self.multi = len(sort_keys) > 1
        self.sort_keys = list(sort_keys) if self.multi else []

    @log_time
    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none", zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Sort order"
        self.border_subtitle = subtitle_keys(
            ("M", "Toggle multiple"), ("X", "Close")
        )

        for o in sort_orders:
            b = Binding(o.key_asc, f"select_order('{o.id}', True)")
            self._bindings._add_binding(b)

            b = Binding(o.key_desc, f"select_order('{o.id}', False)")
            self._bindings._add_binding(b)

        self.draw_table()

    @log_time
    def draw_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)

        labels = {
            k.order.id: f"{i + 1}{'' if k.is_asc else '↑'}"
            for i, k in enumerate(self.sort_keys)
        }
        # in multi mode order names shift right to make room for position
        # prefix, so they stay aligned with each other
        indent = (
            max([2, *(len(label) for label in labels.values())]) + 1
            if self.multi
            else 0
        )

        table.add_column(" " * indent + "Order", width=ORDER_WIDTH)
        table.add_column("Key (ASC | DESC)")

        for o in sort_orders:
            label = labels.get(o.id, "")
            table.add_row(
                Text.assemble(
                    (label, "bold"), " " * (indent - len(label)), o.name
                ),
                Text(str(f"   {o.key_asc} | {o.key_desc}"), justify="center"),
            )

    @log_time
    def action_toggle_multi(self) -> None:
        # chain always starts from scratch: first selected order replaces
        # current sorting
        self.multi = not self.multi
        self.sort_keys = []
        self.draw_table()

    @log_time
    def action_select_order(self, sort_id, is_asc):
        order = next(x for x in sort_orders if x.id == sort_id)

        if not self.multi:
            self.post_message(SortOrderUpdatedEvent((SortKey(order, is_asc),)))
            self.parent.dismiss(False)
            return

        index = next(
            (i for i, k in enumerate(self.sort_keys) if k.order.id == sort_id),
            None,
        )

        if index is None:
            self.sort_keys.append(SortKey(order, is_asc))
        elif self.sort_keys[index].is_asc == is_asc:
            # same key pressed again: remove order from chain
            del self.sort_keys[index]
        else:
            # opposite direction: flip it in place
            self.sort_keys[index] = SortKey(order, is_asc)

        self.draw_table()

        # keep current sorting if chain was emptied
        if self.sort_keys:
            self.post_message(
                SortOrderUpdatedEvent(tuple(self.sort_keys), notify=False)
            )

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
