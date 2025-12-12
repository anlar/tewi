import math
from typing import ClassVar, Optional

from textual import events, on
from textual.binding import Binding, BindingType
from textual.reactive import reactive
from textual.widgets import ListItem, ListView

from ...torrent.models import Torrent
from ...util.log import log_time
from ..messages import (
    ChangeTorrentPriorityCommand,
    Notification,
    OpenAddTorrentCommand,
    OpenEditTorrentCommand,
    OpenFilterCommand,
    OpenSearchCommand,
    OpenSortOrderCommand,
    OpenTorrentInfoCommand,
    OpenUpdateTorrentCategoryCommand,
    OpenUpdateTorrentLabelsCommand,
    PageChangedEvent,
    ReannounceTorrentCommand,
    RemoveTorrentCommand,
    SearchStateChangedEvent,
    StartAllTorrentsCommand,
    StopAllTorrentsCommand,
    ToggleTorrentCommand,
    TorrentRemovedEvent,
    TorrentTrashedEvent,
    TrashTorrentCommand,
    VerifyTorrentCommand,
)
from ..models import PageState
from ..widget.torrent_item import (
    TorrentItem,
    TorrentItemCard,
    TorrentItemCompact,
    TorrentItemOneline,
)


class TorrentListItem(ListItem):
    """List item wrapper for TorrentItem with cached torrent ID for fast
    comparison."""

    def __init__(self, *args, torrent_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.torrent_id = torrent_id  # Cache for fast is_equal_to_page checks


class TorrentListViewPanel(ListView):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("k", "cursor_up", "[Navigation] Move up"),
        Binding("j", "cursor_down", "[Navigation] Move down"),
        Binding("g", "move_top", "[Navigation] Go to first item"),
        Binding("home", "move_top", "[Navigation] Go to first item"),
        Binding("G", "move_bottom", "[Navigation] Go to last item"),
        Binding("end", "move_bottom", "[Navigation] Go to last item"),
        Binding("enter,l,right", "select_cursor", "[Navigation] Open"),
        Binding("a", "add_torrent", "[Torrent] Add"),
        Binding("e", "edit_torrent", "[Torrent] Edit"),
        Binding("L", "update_torrent_labels", "[Torrent] Update labels"),
        Binding("C", "update_torrent_category", "[Torrent] Set category"),
        Binding("s", "sort_order", "[Torrent] Sort order"),
        Binding("f", "filter", "[Torrent] Filter"),
        Binding("p", "change_priority", "[Torrent] Change priority"),
        Binding("space", "toggle_torrent", "[Torrent] Toggle state"),
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

    r_torrents: list[Torrent] | None = reactive(None)

    # Search state
    search_term = ""
    search_idx = 0  # search hits starts with 1
    search_active = False

    @log_time
    def __init__(
        self,
        id: str,
        page_size: str,
        view_mode: str,
        capability_set_priority: bool,
        capability_label: bool,
        capability_category: bool,
    ) -> None:
        self.page_size = page_size
        self.view_mode = view_mode
        self.capability_set_priority = capability_set_priority
        self.capability_label = capability_label
        self.capability_category = capability_category

        super().__init__(id=id)

    @log_time
    def watch_r_torrents(self, new_r_torrents):
        if new_r_torrents:
            self.update_page(torrents=new_r_torrents)
        else:
            self.update_page(torrents=[])

    @log_time
    def is_equal_to_page(self, torrents) -> bool:
        """Check if current page displays the same torrents (optimized with
        cached IDs)."""
        items = self.children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            # Use cached torrent_id for fast comparison instead of
            # accessing widget internals
            if torrent.hash != items[i].torrent_id:
                return False

        return True

    @log_time
    def next_page(self, forward: bool) -> None:
        hl_torrent_id = self.get_hl_torrent_id()

        if hl_torrent_id:
            for i, item in enumerate(self.r_torrents):
                if item.hash == hl_torrent_id:
                    if forward is True:
                        if i + 1 < len(self.r_torrents):
                            next_torrent_id = self.r_torrents[i + 1].hash
                        else:
                            next_torrent_id = None
                    else:
                        if i > 0:
                            next_torrent_id = self.r_torrents[i - 1].hash
                        else:
                            next_torrent_id = None

        if next_torrent_id:
            self.update_page(self.r_torrents, next_torrent_id)

    @log_time
    def update_page(
        self,
        torrents: list[Torrent],
        hl_torrent_id: int = None,
        force: bool = False,
    ) -> None:
        if hl_torrent_id is None:
            hl_torrent_id = self.get_hl_torrent_id()

        if hl_torrent_id is None:
            torrent_idx = None
        else:
            torrent_idx = next(
                (
                    i
                    for i, item in enumerate(torrents)
                    if item.hash == hl_torrent_id
                ),
                None,
            )

        if torrent_idx is None:
            page = 0
        else:
            page = torrent_idx // self.page_size

        self.draw_page(torrents, page, hl_torrent_id, force)

    @log_time
    def draw_page(self, torrents, page, torrent_id, force) -> None:
        """Draw a page of torrents with optimized widget recycling.

        Performance optimization: Reuse existing widgets when possible
        instead of recreating them, which is expensive (100+ ms for 50
        items).
        """

        page_torrents = torrents[
            page * self.page_size : (page * self.page_size + self.page_size)
        ]
        existing_widgets = list(self.children)

        # Fast path 1: Same page, same torrents - just update data
        if not force and self.is_equal_to_page(page_torrents):
            with self.app.batch_update():
                for i, torrent in enumerate(page_torrents):
                    existing_widgets[i]._nodes[0].update_torrent(torrent)

                    if torrent_id == torrent.hash:
                        self.index = self.validate_index(i)

        # Fast path 2: Different page but same widget count - RECYCLE widgets
        elif not force and len(existing_widgets) == len(page_torrents):
            hl_idx = None

            with self.app.batch_update():
                for i, torrent in enumerate(page_torrents):
                    # Reuse existing widget, update its data and cached ID
                    widget = existing_widgets[i]
                    widget.torrent_id = torrent.hash  # Update cached ID
                    widget._nodes[0].update_torrent(
                        torrent
                    )  # Update torrent data

                    if torrent.hash == torrent_id:
                        hl_idx = i

            # Update highlight
            self.index = self.validate_index(hl_idx)

            # Update page state
            state = PageState(current=page, total=self.total_pages(torrents))
            self.post_message(PageChangedEvent(state))

        # Slow path: Different widget count or forced - recreate everything
        else:
            torrent_widgets = []
            hl_idx = None

            for i, t in enumerate(page_torrents):
                item = self.create_item(t)
                list_item = TorrentListItem(
                    item, torrent_id=t.hash
                )  # Pass cached ID

                if t.hash == torrent_id:
                    hl_idx = i
                    list_item.highlighted = True

                torrent_widgets.append(list_item)

            self.clear()
            self.insert(0, torrent_widgets)

            # select
            self.index = self.validate_index(hl_idx)

            state = PageState(current=page, total=self.total_pages(torrents))

            self.post_message(PageChangedEvent(state))

    @log_time
    def total_pages(self, torrents) -> int:
        if len(torrents) == 0:
            return 0
        else:
            return math.ceil(len(torrents) / self.page_size)

    @log_time
    def create_item(self, torrent) -> TorrentItem:
        if self.view_mode == "card":
            item = TorrentItemCard(torrent)
        elif self.view_mode == "compact":
            item = TorrentItemCompact(torrent)
        elif self.view_mode == "oneline":
            item = TorrentItemOneline(torrent)

        return item

    # Actions

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:
        """Check if an action may run."""
        if action == "change_priority":
            return self.capability_set_priority

        if action == "update_torrent_labels":
            return self.capability_label

        if action == "update_torrent_category":
            return self.capability_category

        return True

    # Actions: movement

    @log_time
    def action_move_top(self) -> None:
        if len(self.children) > 0:
            self.index = 0

    @log_time
    def action_move_bottom(self) -> None:
        if len(self.children) > 0:
            self.index = len(self.children) - 1

    @log_time
    def action_cursor_down(self) -> None:
        if self.index == len(self.children) - 1:
            self.next_page(True)
        else:
            super().action_cursor_down()

    @log_time
    def action_cursor_up(self) -> None:
        if self.index == 0:
            self.next_page(False)
        else:
            super().action_cursor_up()

    # Actions: torrent

    @log_time
    def action_edit_torrent(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenEditTorrentCommand(torrent))

    @log_time
    def action_update_torrent_labels(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenUpdateTorrentLabelsCommand(torrent))

    @log_time
    def action_update_torrent_category(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenUpdateTorrentCategoryCommand(torrent))

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
            self.post_message(
                ToggleTorrentCommand(torrent.hash, torrent.status)
            )

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
    def action_filter(self) -> None:
        self.post_message(OpenFilterCommand())

    @log_time
    def action_change_priority(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(
                ChangeTorrentPriorityCommand(torrent.hash, torrent.priority)
            )

    @log_time
    def action_toggle_view_mode(self) -> None:
        if self.view_mode == "card":
            self.view_mode = "compact"
        elif self.view_mode == "compact":
            self.view_mode = "oneline"
        elif self.view_mode == "oneline":
            self.view_mode = "card"

        self.update_page(self.r_torrents, force=True)

    # Actions: Search

    @log_time
    def action_search(self) -> None:
        # Reset search state when opening search dialog
        self._reset_search()
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

        total = sum(1 for i in self.r_torrents if search_term in i.name.lower())

        # First search range
        for i in range1:
            if search_term in self.r_torrents[i].name.lower():
                self._select_found_torrent(i)
                self._update_search_idx(total, forward)
                self.post_message(
                    SearchStateChangedEvent(self.search_idx, total)
                )
                return

        # Second search range (wrap around)
        for i in range2:
            if search_term in self.r_torrents[i].name.lower():
                self._select_found_torrent(i)
                self._update_search_idx(total, forward)
                self.post_message(
                    SearchStateChangedEvent(self.search_idx, total)
                )
                return

        # If no match found, show notification
        self.post_message(Notification(f"No torrents matching '{search_term}'"))

    def _update_search_idx(self, total: int, forward: bool) -> None:
        if forward:
            if self.search_idx == total:
                self.search_idx = 1
            else:
                self.search_idx += 1
        else:
            if self.search_idx == 1:
                self.search_idx = total
            else:
                self.search_idx -= 1

    @log_time
    def _select_found_torrent(self, index: int) -> None:
        self.update_page(self.r_torrents, self.r_torrents[index].hash)

    @log_time
    def search_torrent(self, search_term: str) -> None:
        if search_term:
            self.search_term = search_term
            self.search_active = True
            self._search_torrent(search_term, forward=True)

    @log_time
    def _reset_search(self) -> None:
        self.search_active = False
        self.search_idx = 0
        self.search_term = ""

    @log_time
    def on_key(self, event: events.Key) -> None:
        """Reset search status on any key press that are not search-related"""
        if event.key != "n" and event.key != "N":
            self._reset_search()
            self.post_message(SearchStateChangedEvent())

    # Handlers

    @log_time
    @on(ListView.Selected)
    def handle_selected(self, event: ListView.Selected) -> None:
        torrent_id = event.item._nodes[0].torrent.hash
        self.post_message(OpenTorrentInfoCommand(torrent_id))

    @log_time
    @on(TorrentRemovedEvent)
    def handle_torrent_removed_event(self, event: TorrentRemovedEvent) -> None:
        self._remove_child(event.torrent_hash)

    @log_time
    @on(TorrentTrashedEvent)
    def handle_torrent_trashed_event(self, event: TorrentRemovedEvent) -> None:
        self._remove_child(event.torrent_hash)

    @log_time
    def _remove_child(self, torrent_hash: str) -> None:
        for i, child in enumerate(self.children):
            if torrent_hash == child._nodes[0].torrent.hash:
                self.remove_items([i])

    # Common helpers

    @log_time
    def torrent_idx(self, torrent) -> Optional[int]:
        return next(
            (
                idx
                for idx, t in enumerate(self.r_torrents)
                if t.hash == torrent.hash
            ),
            None,
        )

    @log_time
    def get_hl_torrent(self) -> Optional[int]:
        if (hl_item := self.highlighted_child) is not None:
            return hl_item._nodes[0].torrent

    @log_time
    def get_hl_torrent_id(self) -> Optional[int]:
        if (hl_torrent := self.get_hl_torrent()) is not None:
            return hl_torrent.hash
