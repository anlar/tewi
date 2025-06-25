from typing import ClassVar
from textual import on, work

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
            hl_item = self.highlighted_child

            if hl_item is None:
                hl_torrent_id = None
            else:
                hl_torrent_id = hl_item._nodes[0].torrent.id

            if hl_item is None:
                torrent_idx = None
            else:
                hl_idx = hl_item._nodes[0].torrent.id
                torrent_idx = next((i for i, item in enumerate(new_r_torrents) if item.id == hl_idx), None)

            if torrent_idx is None:
                page = 0
            else:
                page = torrent_idx // self.page_size

            self.draw_page(new_r_torrents, page, hl_torrent_id)

    def draw_page(self, torrents, page, torrent_id) -> None:

        page_torrents = torrents[page * self.page_size:(page * self.page_size + self.page_size)]

        # draw

        torrent_widgets = []

        hl_idx = None
        idx = 0
        new_child = None

        for t in page_torrents:
            item = self.create_item(t)
            list_item = ListItem(item)

            if t.id == torrent_id:
                hl_idx = idx
                list_item.highlighted = True
            else:
                idx = idx + 1

            torrent_widgets.append(list_item)

        self.clear()
        self.extend(torrent_widgets)

        # select

        self.index = self.validate_index(hl_idx)

    @on(ListView.Highlighted)
    def handle_hl(self, event: ListView.Highlighted) -> None:
        self.post_message(Notification(f"CAUGHT"))

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

    def action_cursor_down(self) -> None:
        old_idx = self.index

        super().action_cursor_down()

        if old_idx == self.index:
            self.post_message(Notification("To next page"))
