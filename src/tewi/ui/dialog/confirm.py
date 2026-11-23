import textwrap

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from ...util.log import log_time
from ..util import plain_text, subtitle_keys

# Width of dialog text: dialog width without border and padding
TEXT_WIDTH = 56


class ConfirmDialog(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "confirm", "[Confirmation] Yes"),
        Binding("n,x,escape", "close", "[Confirmation] No"),
    ]

    @log_time
    def __init__(
        self,
        message: str,
        description: str = None,
        items: list[str] | None = None,
    ) -> None:
        """
        Args:
            message: Question to confirm
            description: Optional explanation below question
            items: Optional list below description (e.g. names of
                torrents to remove), shown literally as it may contain
                remote text
        """
        self.message = message
        self.description = description
        self.items = items
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield ConfirmWidget(self.message, self.description, self.items)

    @log_time
    def action_confirm(self) -> None:
        self.dismiss(True)

    @log_time
    def action_close(self) -> None:
        self.dismiss(False)


class ConfirmWidget(Static):
    @log_time
    def __init__(
        self,
        message: str,
        description: str = None,
        items: list[str] | None = None,
    ) -> None:
        self.message = message
        self.description = description
        self.items = items
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield Label(self.message)

        if self.description:
            # empty space between message and description
            yield Label("")
            for line in textwrap.wrap(self.description, TEXT_WIDTH):
                yield Label(line)

        if self.items:
            yield Label("")
            for item in self.items:
                # Single line per item: Label ignores Text no_wrap option
                text = plain_text(f"• {item}")
                text.truncate(TEXT_WIDTH, overflow="ellipsis")
                yield Label(text)

    @log_time
    def on_mount(self):
        self.border_title = "Confirmation"
        self.border_subtitle = subtitle_keys(("Y", "Yes"), ("N", "No"))
