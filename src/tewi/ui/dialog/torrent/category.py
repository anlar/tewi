from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, Select, Button
from textual.app import ComposeResult

from ....message import UpdateTorrentCategoryCommand
from ....util.decorator import log_time


class UpdateTorrentCategoryDialog(ModalScreen):

    @log_time
    def __init__(self, torrent, categories: list[str]):
        self.torrent = torrent
        self.categories = categories
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield UpdateTorrentCategoryWidget(self.torrent, self.categories)


class UpdateTorrentCategoryWidget(Static):

    BINDINGS = [
            Binding("escape,x", "close", "[Navigation] Close"),
            Binding("enter", "set_category", "[Torrent] Set category", priority=True),
            ]

    @log_time
    def __init__(self, torrent, categories: list[str]):
        self.torrent = torrent
        self.categories = categories
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        # Build options: (display_name, value)
        options = [("(No category)", None)]
        options.extend((cat, cat) for cat in self.categories)

        # Set initial value to current category
        initial_value = self.torrent.category if hasattr(self.torrent, 'category') else None

        yield Select(options, id="category-select",
                     value=initial_value,
                     allow_blank=False, compact=True)

    @log_time
    def on_mount(self) -> None:
        self.border_title = 'Set category'
        self.border_subtitle = '(Enter) Set / (X) Close'

    @log_time
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "set-button":
            self.action_set_category()

    @log_time
    def action_set_category(self) -> None:
        select = self.query_one("#category-select", Select)
        category_value = select.value

        self.post_message(UpdateTorrentCategoryCommand(
            self.torrent.id, category_value))

        self.parent.dismiss(False)

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss(False)
