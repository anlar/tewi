from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from ....util.log import log_time
from ...messages import FilterTagUpdatedEvent
from ...models import TagType
from ...util import plain_text, subtitle_keys


class FilterTagDialog(ModalScreen):
    @log_time
    def __init__(
        self, tag_type: TagType, counts: dict[str, int], current: str | None
    ):
        self.tag_type = tag_type
        self.counts = counts
        self.current = current
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield FilterTagWidget(self.tag_type, self.counts, self.current)


class FilterTagWidget(Static):
    BINDINGS = [
        Binding("k", "cursor_up", "[Navigation] Cursor up"),
        Binding("j", "cursor_down", "[Navigation] Cursor down"),
        Binding("escape,x", "close", "[Navigation] Close"),
    ]

    @log_time
    def __init__(
        self, tag_type: TagType, counts: dict[str, int], current: str | None
    ):
        """
        Args:
            tag_type: Filter by category or label
            counts: Torrent count per category/label name, in display order
            current: Name of currently selected category/label
        """
        self.tag_type = tag_type
        self.counts = counts
        self.current = current
        # List item index to category/label name, None for "Any" item
        self.names: list[str | None] = [None, *counts]
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        items = [ListItem(Label("(Any)"))]

        for name, count in self.counts.items():
            text = Text.assemble(plain_text(name), (f" ({count})", "dim"))
            items.append(ListItem(Label(text)))

        index = (
            self.names.index(self.current) if self.current in self.counts else 0
        )

        yield ListView(*items, initial_index=index)

    @log_time
    def on_mount(self) -> None:
        self.border_title = f"Filter by {self.tag_type.value.lower()}"
        self.border_subtitle = subtitle_keys(
            ("Enter", "Filter"), ("X", "Close")
        )

    @log_time
    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    @log_time
    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    @log_time
    @on(ListView.Selected)
    def select(self, event: ListView.Selected) -> None:
        name = self.names[event.list_view.index]

        self.post_message(FilterTagUpdatedEvent(self.tag_type, name))

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
