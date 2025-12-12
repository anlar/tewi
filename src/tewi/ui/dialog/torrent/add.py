from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from ....util import clipboard
from ....util.log import log_time
from ....util.misc import is_torrent_link
from ...messages import AddTorrentCommand
from ...util import print_size, subtitle_keys
from ...widget.common import ReactiveLabel


class AddTorrentDialog(ModalScreen[None]):
    @log_time
    def __init__(self, download_dir: str, download_dir_free_space: int):
        self.download_dir = download_dir
        self.download_dir_free_space = download_dir_free_space
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield AddTorrentWidget(self.download_dir, self.download_dir_free_space)


class AddTorrentWidget(Static):
    r_download_dir = reactive("")

    BINDINGS = [
        Binding("enter", "add", "[Torrent] Add torrent", priority=True),
        Binding("escape", "close", "[Torrent] Close"),
    ]

    @log_time
    def __init__(self, download_dir: str, download_dir_free_space: int):
        self.download_dir = download_dir
        self.download_dir_free_space = download_dir_free_space
        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        yield ReactiveLabel().data_bind(name=AddTorrentWidget.r_download_dir)
        yield TextArea()

    @log_time
    def on_mount(self) -> None:
        self.border_title = "Add torrent (local file, magnet link, URL)"
        self.border_subtitle = subtitle_keys(("Enter", "Add"), ("ESC", "Close"))

        free_space = print_size(self.download_dir_free_space)

        self.r_download_dir = (
            f"Destination folder: {self.download_dir} ({free_space} Free)"
        )

        text_area = self.query_one(TextArea)

        link = self.get_link_from_clipboard()

        if link:
            text_area.load_text(link)
        else:
            text_area.load_text("~/")

        text_area.cursor_location = text_area.document.end

    @log_time
    def get_link_from_clipboard(self) -> str:
        text = clipboard.paste()

        if text and is_torrent_link(text):
            return text

        return None

    @log_time
    def action_add(self) -> None:
        value = self.query_one(TextArea).text

        self.post_message(AddTorrentCommand(value))
        self.parent.dismiss()

    @log_time
    def action_close(self) -> None:
        self.parent.dismiss()
