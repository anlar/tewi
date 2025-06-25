from typing import ClassVar

from textual import on

from textual.binding import Binding, BindingType
from textual.widgets import ListView, ListItem
from textual.reactive import reactive

from ..widget.torrent_item import TorrentItem, TorrentItemCard, TorrentItemCompact, TorrentItemOneline

# from ...message import Notification
from ...message import OpenTorrentInfoCommand, OpenAddTorrentCommand, ToggleTorrentCommand


class TorrentListViewPanel(ListView):

    BINDINGS: ClassVar[list[BindingType]] = [
            Binding("k", "cursor_up", "[Navigation] Move up"),
            Binding("j", "cursor_down", "[Navigation] Move down"),

            Binding("g", "move_top", "[Navigation] Go to first item"),
            Binding("home", "move_top", "[Navigation] Go to first item"),
            Binding("G", "move_bottom", "[Navigation] Go to last item"),
            Binding("end", "move_bottom", "[Navigation] Go to last item"),

            Binding("enter,l", "select_cursor", "[Navigation] Open"),

            Binding("a", "add_torrent", "[Torrent] Add"),
            Binding("p", "toggle_torrent", "[Torrent] Toggle state"),

            Binding("m", "toggle_view_mode", "[UI] Toggle view mode"),
    ]

    r_torrents = reactive(None)

    def __init__(self, id: str, page_size: str, view_mode: str) -> None:
        self.page_size = page_size
        self.view_mode = view_mode
        super().__init__(id=id)

    def watch_r_torrents(self, new_r_torrents):
        if new_r_torrents:
            self.update_page(torrents=new_r_torrents)

    def is_equal_to_page(self, torrents) -> bool:
        items = self.children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i]._nodes[0].torrent.id:
                return False

        return True

    def next_page(self, forward: bool) -> None:
        hl_torrent_id = self.get_hl_torrent_id()

        if hl_torrent_id:
            for i, item in enumerate(self.r_torrents):
                if item.id == hl_torrent_id:
                    if forward is True:
                        if i + 1 < len(self.r_torrents):
                            next_torrent_id = self.r_torrents[i + 1].id
                        else:
                            next_torrent_id = None
                    else:
                        if i > 0:
                            next_torrent_id = self.r_torrents[i - 1].id
                        else:
                            next_torrent_id = None

        if next_torrent_id:
            self.update_page(self.r_torrents, next_torrent_id)

    def update_page(self, torrents: list, hl_torrent_id: int = None, force: bool = False) -> None:
        # self.post_message(Notification(f"update_page: {hl_torrent_id}"))
        if hl_torrent_id is None:
            hl_torrent_id = self.get_hl_torrent_id()

        if hl_torrent_id is None:
            torrent_idx = None
        else:
            torrent_idx = next((i for i, item in enumerate(torrents) if item.id == hl_torrent_id), None)

        if torrent_idx is None:
            page = 0
        else:
            page = torrent_idx // self.page_size

        self.draw_page(torrents, page, hl_torrent_id, force)

    def draw_page(self, torrents, page, torrent_id, force) -> None:
        # self.post_message(Notification(f"draw_page: page {page}, torrent_id {torrent_id}"))

        page_torrents = torrents[page * self.page_size:(page * self.page_size + self.page_size)]

        if not force and self.is_equal_to_page(page_torrents):
            torrent_widgets = self.children

            for i, torrent in enumerate(page_torrents):
                torrent_widgets[i]._nodes[0].update_torrent(torrent)
        else:

            # draw

            torrent_widgets = []

            hl_idx = None
            idx = 0

            for t in page_torrents:
                item = self.create_item(t)
                list_item = ListItem(item)

                if t.id == torrent_id:
                    hl_idx = idx
                    list_item.highlighted = True
                    # self.post_message(Notification(f"HL: {t.name}"))
                else:
                    idx = idx + 1

                torrent_widgets.append(list_item)
                # self.post_message(Notification(f"ITEM: {list_item.highlighted}"))

            self.clear()
            self.insert(0, torrent_widgets)

            # select

            self.index = self.validate_index(hl_idx)
            # self.post_message(Notification(f"HL index: {self.index}"))

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
            # self.post_message(Notification("Go to zero"))

    def action_move_bottom(self) -> None:
        if len(self.children) > 0:
            self.index = len(self.children) - 1
            # self.post_message(Notification("Go to bottom"))

    def action_cursor_down(self) -> None:
        if self.index == len(self.children) - 1:
            # self.post_message(Notification("To next page"))
            self.next_page(True)
        else:
            super().action_cursor_down()

    def action_cursor_up(self) -> None:
        if self.index == 0:
            # self.post_message(Notification("To prev page"))
            self.next_page(False)
        else:
            super().action_cursor_up()

    def on_list_view_highlighted(self, event) -> None:
        pass
        # self.post_message(Notification(f"HL HIT: {event.control.index}"))

    def get_hl_torrent(self) -> int:
        hl_item = self.highlighted_child

        if hl_item is None:
            return None
        else:
            return hl_item._nodes[0].torrent

    def get_hl_torrent_id(self) -> int:
        hl_torrent = self.get_hl_torrent()

        if hl_torrent is None:
            return None
        else:
            return hl_torrent.id

    # Actions

    @on(ListView.Selected)
    def handle_selected(self, event: ListView.Selected) -> None:
        torrent_id = event.item._nodes[0].torrent.id
        self.post_message(OpenTorrentInfoCommand(torrent_id))

    def action_add_torrent(self) -> None:
        self.post_message(OpenAddTorrentCommand())

    def action_toggle_torrent(self) -> None:
        torrent = self.get_hl_torrent()

        if torrent:
            self.post_message(ToggleTorrentCommand(torrent.id, torrent.status))

    def action_toggle_view_mode(self) -> None:
        if self.view_mode == 'card':
            self.view_mode = 'compact'
        elif self.view_mode == 'compact':
            self.view_mode = 'oneline'
        elif self.view_mode == 'oneline':
            self.view_mode = 'card'

        self.update_page(self.r_torrents, force=True)
