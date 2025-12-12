from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ....torrent.models import TorrentCategory
from ....util.log import log_time
from ...messages import UpdateTorrentCategoryCommand
from ...util import subtitle_keys


class UpdateTorrentCategoryDialog(ModalScreen):
    @log_time
    def __init__(self, torrent, categories: list[TorrentCategory]):
        self.torrent = torrent
        self.categories = categories
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield UpdateTorrentCategoryWidget(self.torrent, self.categories)


class UpdateTorrentCategoryWidget(Static):
    BINDINGS = [
        Binding("k", "cursor_up", "[Navigation] Cursor up"),
        Binding("j", "cursor_down", "[Navigation] Cursor down"),
        Binding("escape,x", "close", "[Navigation] Close"),
        Binding(
            "enter", "set_category", "[Torrent] Set category", priority=True
        ),
    ]

    @log_time
    def __init__(self, torrent, categories: list[TorrentCategory]):
        self.torrent = torrent
        self.categories = categories

        # Store category name to value mapping (None for "No category")
        self.category_map = {None: None}

        for cat in categories:
            self.category_map[cat.name] = cat.name

        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row", zebra_stripes=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Set category"
        self.border_subtitle = subtitle_keys(("Enter", "Set"), ("X", "Close"))

        table = self.query_one(DataTable)

        table.add_columns("Name", "Save path")

        # Add "No category" as first row
        table.add_row("(No category)", "", key=None)

        # Add all categories
        current_category = (
            self.torrent.category if hasattr(self.torrent, "category") else None
        )
        cursor_row = 0

        for idx, cat in enumerate(self.categories):
            table.add_row(cat.name, cat.save_path or "", key=cat.name)
            # Track which row has the current category
            if current_category == cat.name:
                cursor_row = idx + 1  # +1 because "No category" is first row

        # Set cursor to current category row
        if cursor_row < table.row_count:
            table.move_cursor(row=cursor_row)

    @log_time
    def action_cursor_up(self) -> None:
        table = self.query_one(DataTable)
        table.action_cursor_up()

    @log_time
    def action_cursor_down(self) -> None:
        table = self.query_one(DataTable)
        table.action_cursor_down()

    @log_time
    def action_set_category(self) -> None:
        table = self.query_one(DataTable)

        # Get the selected row key (which is the category name or None)
        # coordinate_to_cell_key returns (RowKey, ColumnKey)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        category_value = row_key.value

        self.post_message(
            UpdateTorrentCategoryCommand(self.torrent.hash, category_value)
        )

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
