from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from ....util.log import log_time
from ...messages import FilterTagUpdatedEvent
from ...models import TagType
from ...util import plain_text, subtitle_keys
from ...widget.common import VimOptionList


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
        # Option index to category/label name, None for "Any" option
        self.names: list[str | None] = [None, *counts]
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        # OptionList renders only visible lines, so it opens fast with
        # thousands of labels
        options = [Text("(Any)")]

        for name, count in self.counts.items():
            options.append(
                Text.assemble(
                    plain_text(name),
                    (f" ({count})", "dim"),
                    no_wrap=True,
                    overflow="ellipsis",
                )
            )

        yield VimOptionList(*options)

    @log_time
    def on_mount(self) -> None:
        self.border_title = f"Filter by {self.tag_type.value.lower()}"
        self.border_subtitle = subtitle_keys(
            ("Enter", "Filter"), ("X", "Close")
        )

        if self.current in self.counts:
            option_list = self.query_one(OptionList)
            option_list.highlighted = self.names.index(self.current)

    @log_time
    @on(OptionList.OptionSelected)
    def select(self, event: OptionList.OptionSelected) -> None:
        # Selection is posted as message, so keys pressed before it's
        # handled may already have closed dialog (e.g. Enter twice) or
        # moved cursor: second dismiss would pop main screen
        if not self.parent.is_current:
            return

        name = self.names[event.option_index]

        self.post_message(FilterTagUpdatedEvent(self.tag_type, name))

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
