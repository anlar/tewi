import math

from typing import ClassVar, Optional

from textual import on

from textual.binding import Binding, BindingType
from textual.widgets import ListView, ListItem
from textual.reactive import reactive

from ...common import PageState
from ..widget.torrent_item import TorrentItem, TorrentItemCard, TorrentItemCompact, TorrentItemOneline
from ...util.decorator import log_time

# from ...message import Notification
from ...message import OpenTorrentInfoCommand, OpenAddTorrentCommand, ToggleTorrentCommand, \
        VerifyTorrentCommand, ReannounceTorrentCommand, RemoveTorrentCommand, TorrentRemovedEvent, \
        TrashTorrentCommand, TorrentTrashedEvent, Notification, OpenSearchCommand, \
        StartAllTorrentsCommand, StopAllTorrentsCommand, OpenUpdateTorrentLabelsCommand, OpenSortOrderCommand, \
        PageChangedEvent


class TorrentListItem(ListItem):

    @log_time
    def watch_highlighted(self, value: bool) -> None:
        super().watch_highlighted(value)

        if self._nodes:
            self._nodes[0].set_class(value, "-highlight")


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
            Binding("L", "update_torrent_labels", "[Torrent] Update labels"),
            Binding("s", "sort_order", "[Torrent] Sort order"),

            Binding("p", "toggle_torrent", "[Torrent] Toggle state"),
            Binding("r", "remove_torrent", "[Torrent] Remove"),
            Binding("R", "trash_torrent", "[Torrent] Trash with data"),
            Binding("v", "verify_torrent", "[Torrent] Verify"),
            Binding("c", "reannounce_torrent", "[Torrent] Reannounce"),

            Binding("y", "start_all_torrents", "[Torrent] Start all"),
            Binding("Y", "stop_all_torrents", "[Torrent] Stop all"),

            Binding("m", "toggle_view_mode", "[UI] Toggle view mode"),
            Binding("/", "search", "[Search] Open"),
            Binding("n", "search_next", "[Search] Next result"),
            Binding("N", "search_previous", "[Search] Previous result"),
    ]

    r_torrents = reactive(None)

    # Search state
    search_term = ""
    search_active = False

    @log_time
    def __init__(self, id: str, page_size: str, view_mode: str) -> None:
        self.page_size = page_size
        self.view_mode = view_mode
        super().__init__(id=id)

    @log_time
    def watch_r_torrents(self, new_r_torrents):
        if new_r_torrents:
            self.update_page(torrents=new_r_torrents)

    @log_time
    def is_equal_to_page(self, torrents) -> bool:
        items = self.children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i]._nodes[0].torrent.id:
                return False

        return True

    @log_time
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

    @log_time
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

    @log_time
    def draw_page(self, torrents, page, torrent_id, force) -> None:
        # self.post_message(Notification(f"draw_page: page {page}, torrent_id {torrent_id}"))

        page_torrents = torrents[page * self.page_size:(page * self.page_size + self.page_size)]

        if not force and self.is_equal_to_page(page_torrents):
            torrent_widgets = self.children

            for i, torrent in enumerate(page_torrents):
                torrent_widgets[i]._nodes[0].update_torrent(torrent)

                if torrent_id == torrent.id:
                    self.index = self.validate_index(i)
        else:

            # draw

            torrent_widgets = []

            hl_idx = None
            idx = 0

            for t in page_torrents:
                item = self.create_item(t)
                list_item = TorrentListItem(item)

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

            state = PageState(current=page,
                              total=self.total_pages(torrents))

            self.post_message(PageChangedEvent(state))

    @log_time
    def total_pages(self, torrents) -> int:
        if len(torrents) == 0:
            return 0
        else:
            return math.ceil(len(torrents) / self.page_size)

    @log_time
    def create_item(self, torrent) -> TorrentItem:
        if self.view_mode == 'card':
            item = TorrentItemCard(torrent)
        elif self.view_mode == 'compact':
            item = TorrentItemCompact(torrent)
        elif self.view_mode == 'oneline':
            item = TorrentItemOneline(torrent)

        return item

    # Actions: movement

    @log_time
    def action_move_top(self) -> None:
        if len(self.children) > 0:
            self.index = 0
            # self.post_message(Notification("Go to zero"))

    @log_time
    def action_move_bottom(self) -> None:
        if len(self.children) > 0:
            self.index = len(self.children) - 1
            # self.post_message(Notification("Go to bottom"))

    @log_time
    def action_cursor_down(self) -> None:
        if self.index == len(self.children) - 1:
            # self.post_message(Notification("To next page"))
            self.next_page(True)
        else:
            super().action_cursor_down()

    @log_time
    def action_cursor_up(self) -> None:
        if self.index == 0:
            # self.post_message(Notification("To prev page"))
            self.next_page(False)
        else:
            super().action_cursor_up()

    # Actions: torrent

    @log_time
    def action_update_torrent_labels(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenUpdateTorrentLabelsCommand(torrent))

    @log_time
    def action_verify_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(VerifyTorrentCommand(torrent_id))

    @log_time
    def action_reannounce_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(ReannounceTorrentCommand(torrent_id))

    @log_time
    def action_toggle_torrent(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(ToggleTorrentCommand(torrent.id, torrent.status))

    @log_time
    def action_remove_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(RemoveTorrentCommand(torrent_id))

    @log_time
    def action_trash_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(TrashTorrentCommand(torrent_id))

    @log_time
    def action_add_torrent(self) -> None:
        self.post_message(OpenAddTorrentCommand())

    @log_time
    def action_start_all_torrents(self) -> None:
        self.post_message(StartAllTorrentsCommand())

    @log_time
    def action_stop_all_torrents(self) -> None:
        self.post_message(StopAllTorrentsCommand())

    @log_time
    def action_sort_order(self) -> None:
        self.post_message(OpenSortOrderCommand())

    @log_time
    def action_toggle_view_mode(self) -> None:
        if self.view_mode == 'card':
            self.view_mode = 'compact'
        elif self.view_mode == 'compact':
            self.view_mode = 'oneline'
        elif self.view_mode == 'oneline':
            self.view_mode = 'card'

        self.update_page(self.r_torrents, force=True)

    # Actions: Search

    @log_time
    def action_search(self) -> None:
        # Reset search state when opening search dialog
        self.search_active = False
        self.search_term = ""
        self.post_message(OpenSearchCommand())

    @log_time
    def action_search_next(self) -> None:
        if not self.search_active or not self.search_term:
            self.post_message(Notification("No active search"))
        else:
            self._search_torrent(self.search_term, forward=True)

    @log_time
    def action_search_previous(self) -> None:
        if not self.search_active or not self.search_term:
            self.post_message(Notification("No active search"))
        else:
            self._search_torrent(self.search_term, forward=False)

    @log_time
    def _search_torrent(self, search_term: str, forward: bool = True) -> None:
        if not search_term or not self.r_torrents:
            return

        search_term = search_term.lower()

        # Get current index if there's a selected item
        if (torrent := self.get_hl_torrent()) is not None:
            current_idx = self.torrent_idx(torrent)
        else:
            current_idx = -1

        if current_idx is None:
            current_idx = -1

        # Determine search range based on direction
        if forward:
            # Search from current+1 to end, then from start to current
            range1 = range(current_idx + 1, len(self.r_torrents))
            range2 = range(0, current_idx + 1)
        else:
            # Search from current-1 to start, then from end to current
            range1 = range(current_idx - 1, -1, -1)
            range2 = range(len(self.r_torrents) - 1, current_idx, -1)

        # First search range
        for i in range1:
            if search_term in self.r_torrents[i].name.lower():
                self._select_found_torrent(i)
                return

        # Second search range (wrap around)
        for i in range2:
            if search_term in self.r_torrents[i].name.lower():
                self._select_found_torrent(i)
                return

        # If no match found, show notification
        self.post_message(Notification(f"No torrents matching '{search_term}'"))

    @log_time
    def _select_found_torrent(self, index: int) -> None:
        self.update_page(self.r_torrents, self.r_torrents[index].id)

    @log_time
    def search_torrent(self, search_term: str) -> None:
        if search_term:
            self.search_term = search_term
            self.search_active = True
            self._search_torrent(search_term, forward=True)

    # Handlers

    @log_time
    @on(ListView.Selected)
    def handle_selected(self, event: ListView.Selected) -> None:
        torrent_id = event.item._nodes[0].torrent.id
        self.post_message(OpenTorrentInfoCommand(torrent_id))

    @log_time
    @on(TorrentRemovedEvent)
    def handle_torrent_removed_event(self, event: TorrentRemovedEvent) -> None:
        self._remove_child(event.torrent_id)

    @log_time
    @on(TorrentTrashedEvent)
    def handle_torrent_trashed_event(self, event: TorrentRemovedEvent) -> None:
        self._remove_child(event.torrent_id)

    @log_time
    def _remove_child(self, torrent_id: int) -> None:
        for i, child in enumerate(self.children):
            if torrent_id == child._nodes[0].torrent.id:
                self.remove_items([i])

    # Common helpers

    @log_time
    def torrent_idx(self, torrent) -> Optional[int]:
        return next((idx for idx, t in enumerate(self.r_torrents) if t.id == torrent.id), None)

    @log_time
    def get_hl_torrent(self) -> Optional[int]:
        if (hl_item := self.highlighted_child) is not None:
            return hl_item._nodes[0].torrent

    @log_time
    def get_hl_torrent_id(self) -> Optional[int]:
        if (hl_torrent := self.get_hl_torrent()) is not None:
            return hl_torrent.id
