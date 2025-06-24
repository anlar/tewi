from typing import ClassVar

from textual.binding import Binding, BindingType
from textual.widgets import ListView, ListItem
from textual.reactive import reactive

from ..widget.torrent_item import TorrentItem, TorrentItemCard, TorrentItemCompact, TorrentItemOneline

from ...message import Notification


class TorrentListViewPanel(ListView):

    BINDINGS: ClassVar[list[BindingType]] = [
            Binding("k", "cursor_up", "[Navigation] Move up"),
            Binding("j", "cursor_down", "[Navigation] Move down"),

            Binding("g", "move_top", "[Navigation] Go to first item"),
            Binding("home", "move_top", "[Navigation] Go to first item"),
            Binding("G", "move_bottom", "[Navigation] Go to last item"),
            Binding("end", "move_bottom", "[Navigation] Go to last item"),
    ]

    r_torrents = reactive(None)

    def __init__(self, id: str, page_size: str, view_mode: str) -> None:
        self.page_size = page_size
        self.view_mode = view_mode
        super().__init__(id=id)

    def watch_r_torrents(self, new_r_torrents):
        if new_r_torrents:
            if len(self.children) == 0:
                self.clear()

                torrent_widgets = []

                for t in new_r_torrents:
                    item = self.create_item(t)

                    torrent_widgets.append(ListItem(item))

                self.extend(torrent_widgets)

    def create_item(self, torrent) -> TorrentItem:
        if self.view_mode == 'card':
            item = TorrentItemCard(torrent)
        elif self.view_mode == 'compact':
            item = TorrentItemCompact(torrent)
        elif self.view_mode == 'oneline':
            item = TorrentItemOneline(torrent)

        return item

    def action_move_top(self) -> None:
        if len(self.children) > 0:
            self.index = 0
            self.post_message(Notification("Go to zero"))

    def action_move_bottom(self) -> None:
        if len(self.children) > 0:
            self.index = len(self.children) - 1
            self.post_message(Notification("Go to bottom"))
