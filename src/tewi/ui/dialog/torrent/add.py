import pyperclip

from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea
from textual.app import ComposeResult
from textual.reactive import reactive

from ....message import AddTorrent
from ....util.print import print_size
from ....util.misc import is_torrent_link
from ...widget.common import ReactiveLabel


class AddTorrentDialog(ModalScreen[None]):

    def __init__(self, download_dir: str, download_dir_free_space: int):
        self.download_dir = download_dir
        self.download_dir_free_space = download_dir_free_space
        super().__init__()

    def compose(self) -> ComposeResult:
        yield AddTorrentWidget(self.download_dir, self.download_dir_free_space)


class AddTorrentWidget(Static):

    r_download_dir = reactive('')

    BINDINGS = [
            Binding("enter", "add", "[Torrent] Add torrent", priority=True),
            Binding("escape", "close", "[Torrent] Close"),
            ]

    def __init__(self, download_dir: str, download_dir_free_space: int):
        self.download_dir = download_dir
        self.download_dir_free_space = download_dir_free_space
        super().__init__()

    def compose(self) -> ComposeResult:
        yield ReactiveLabel().data_bind(
                name=AddTorrentWidget.r_download_dir)
        yield TextArea()

    def on_mount(self) -> None:
        self.border_title = 'Add torrent (local file, magnet link, URL)'
        self.border_subtitle = '(Enter) Add / (ESC) Close'

        free_space = print_size(self.download_dir_free_space)

        self.r_download_dir = f'Destination folder: {self.download_dir} ({free_space} Free)'

        text_area = self.query_one(TextArea)

        link = self.get_link_from_clipboard()

        if link:
            text_area.load_text(link)
        else:
            text_area.load_text('~/')

        text_area.cursor_location = text_area.document.end

    def get_link_from_clipboard(self) -> str:
        try:
            text = pyperclip.paste()

            if text:
                if is_torrent_link(text):
                    return text
        except pyperclip.PyperclipException:
            return None

        return None

    def action_add(self) -> None:
        value = self.query_one(TextArea).text

        self.post_message(AddTorrent(value))
        self.parent.dismiss()

    def action_close(self) -> None:
        self.parent.dismiss()
