from typing import cast

from textual import work
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

# Shown when clipboard has no link
DEFAULT_TEXT = "~/"


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
        self.border_title = (
            "Add torrent (local file, magnet link, URL, info hash)"
        )
        self.border_subtitle = subtitle_keys(("Enter", "Add"), ("ESC", "Close"))

        free_space = print_size(self.download_dir_free_space)

        self.r_download_dir = (
            f"Destination folder: {self.download_dir} ({free_space} Free)"
        )

        text_area = self.query_one(TextArea)
        text_area.load_text(DEFAULT_TEXT)
        text_area.cursor_location = text_area.document.end

        # Clipboard of machine running Tewi is not user's one in web mode
        if not self.app.is_web:
            self.load_link_from_clipboard()

    @work(thread=True, group="clipboard")
    def load_link_from_clipboard(self) -> None:
        """Read link from system clipboard in background thread.

        Clipboard helper program (e.g. xclip) may not respond, which would
        block UI if done in message handler.
        """
        text = clipboard.paste()

        if text and is_torrent_link(text):
            self.app.call_from_thread(self.show_link, text)

    @log_time
    def show_link(self, link: str) -> None:
        """Show link from clipboard, unless user already edited text."""
        # Dialog may be closed while clipboard was read
        if not self.is_mounted:
            return

        text_area = self.query_one(TextArea)

        if text_area.text == DEFAULT_TEXT:
            text_area.load_text(link)
            text_area.cursor_location = text_area.document.end

    @log_time
    def action_add(self) -> None:
        value = self.query_one(TextArea).text

        self.post_message(AddTorrentCommand(value))
        cast(ModalScreen[None], self.parent).dismiss()

    @log_time
    def action_close(self) -> None:
        cast(ModalScreen[None], self.parent).dismiss()
