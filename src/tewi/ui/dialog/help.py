from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ...util.log import log_time
from ..util import subtitle_keys


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
        yield DataTable(cursor_type="none", zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Help"
        self.border_subtitle = subtitle_keys(("X", "Close"))

        table = self.query_one(DataTable)
        table.add_columns("Category", "Key", "Command")

        # Group bindings by (category, command) and collect keys
        command_groups = {}
        for b in filter(lambda x: x.binding.show, self.bindings):
            key = b.binding.key
            description = b.binding.description

            if key == "question_mark":
                key = "?"
            elif key == "quotation_mark":
                key = '"'
            elif key == "slash":
                key = "/"

            if len(key) > 1:
                key = key.title()

            # Split description into category and command
            if description.startswith("["):
                category, _, command = b.binding.description.partition("] ")
                category = category[1:]  # Remove leading [
            else:
                category = "General"
                command = description

            # Group by (category, command) tuple
            group_key = (category, command)
            if group_key not in command_groups:
                command_groups[group_key] = []
            command_groups[group_key].append(key)

        # Sort and combine keys for each command group
        rows = []
        for (category, command), keys in command_groups.items():
            # Sort keys: single-char first, then multi-char
            # (both alphabetically)
            single_char = sorted([k for k in keys if len(k) == 1])
            multi_char = sorted([k for k in keys if len(k) > 1])
            sorted_keys = single_char + multi_char

            # Combine keys with comma and space
            combined_keys = ", ".join(sorted_keys)
            rows.append((category, command, combined_keys))

        # Sort rows by category, then by command
        for category, command, combined_keys in sorted(rows):
            table.add_row(category, combined_keys, command)
