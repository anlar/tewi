import textwrap

from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Label
from textual.app import ComposeResult


class ConfirmDialog(ModalScreen[bool]):

    BINDINGS = [
            Binding("y", "confirm", "[Confirmation] Yes"),
            Binding("n,x,escape", "close", "[Confirmation] No"),
            ]

    def __init__(self, message: str, description: str = None) -> None:
        self.message = message
        self.description = description
        super().__init__()

    def compose(self) -> ComposeResult:
        yield ConfirmWidget(self.message, self.description)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_close(self) -> None:
        self.dismiss(False)


class ConfirmWidget(Static):

    def __init__(self, message: str, description: str = None) -> None:
        self.message = message
        self.description = description
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(self.message)

        if self.description:
            # empty space between message and description
            yield Label('')
            for line in textwrap.wrap(self.description, 56):
                yield Label(line)

    def on_mount(self):
        self.border_title = 'Confirmation'
        self.border_subtitle = '(Y) Yes / (N) No'
