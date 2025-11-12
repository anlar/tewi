from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, DataTable
from textual.app import ComposeResult
from ...util.decorator import log_time


class HelpDialog(ModalScreen[None]):

    BINDINGS = [
            Binding("x,escape", "close", "[Navigation] Close"),
            ]

    @log_time
    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield HelpWidget(self.bindings)

    @log_time
    def action_close(self) -> None:
        self.dismiss()


class HelpWidget(Static):

    @log_time
    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none",
                        zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = 'Help'
        self.border_subtitle = '(X) Close'

        table = self.query_one(DataTable)
        table.add_columns("Category", "Key", "Command")

        # Group and sort bindings by category
        categories = {}
        for b in filter(lambda x: x.binding.show, self.bindings):
            key = b.binding.key
            description = b.binding.description

            if key == 'question_mark':
                key = '?'
            elif key == 'quotation_mark':
                key = '"'
            elif key == 'slash':
                key = '/'

            if len(key) > 1:
                key = key.title()

            # Split description into category and command
            if description.startswith("["):
                category, _, command = b.binding.description.partition("] ")
                category = category[1:]  # Remove leading [
            else:
                category = "General"
                command = description

            if category not in categories:
                categories[category] = []
            categories[category].append((command, key))

        # Sort categories and their commands
        for category in sorted(categories.keys()):
            for command, key in sorted(categories[category]):
                table.add_row(category, key, command)
