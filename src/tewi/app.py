#!/usr/bin/env python3

# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2024  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from .version import __version__

from typing import NamedTuple
import argparse
import logging
import math
import os
import pathlib
import sys

from transmission_rpc import Client
from transmission_rpc.error import TransmissionError
from transmission_rpc.session import Session, SessionStats

from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static, DataTable, ContentSwitcher, \
        TextArea, Input


import pyperclip

from .util.print import print_size
from .util.decorator import log_time
from .ui.dialog.confirm import ConfirmDialog
from .ui.dialog.help import HelpDialog
from .ui.dialog.statistics import StatisticsDialog
from .ui.widget.common import ReactiveLabel
from .ui.widget.torrent_item import TorrentItem, TorrentItemCard, TorrentItemCompact, TorrentItemOneline
from .ui.panel.info import InfoPanel
from .ui.panel.state import StatePanel
from .ui.panel.details import TorrentInfoPanel


logger = logging.getLogger('tewi')


# Common data

class PageState(NamedTuple):
    current: int
    total: int


class SortOrder(NamedTuple):
    id: str
    name: str
    key_asc: str
    key_desc: str
    sort_func: None


class TransmissionSession(NamedTuple):
    session: Session
    session_stats: SessionStats
    torrents_down: int
    torrents_seed: int
    torrents_check: int
    torrents_stop: int
    torrents_complete_size: int
    torrents_total_size: int
    sort_order: SortOrder
    sort_order_asc: bool


sort_orders = [
        SortOrder('age', 'Age', 'a', 'A',
                  lambda t: t.added_date),
        SortOrder('name', 'Name', 'n', 'N',
                  lambda t: t.name.lower()),
        SortOrder('size', 'Size', 'z', 'Z',
                  lambda t: t.total_size),
        SortOrder('status', 'Status', 't', 'T',
                  lambda t: t.status),
        SortOrder('priority', 'Priority', 'i', 'I',
                  lambda t: t.priority),
        SortOrder('queue_order', 'Queue Order', 'o', 'O',
                  lambda t: t.queue_position),
        SortOrder('ratio', 'Ratio', 'r', 'R',
                  lambda t: t.ratio),
        SortOrder('progress', 'Progress', 'p', 'P',
                  lambda t: t.percent_done),
        SortOrder('activity', 'Activity', 'y', 'Y',
                  lambda t: t.activity_date),
        SortOrder('uploaded', 'Uploaded', 'u', 'U',
                  lambda t: t.uploaded_ever),
        SortOrder('peers', 'Peers', 'e', 'E',
                  lambda t: t.peers_connected),
        SortOrder('seeders', 'Seeders', 's', 'S',
                  lambda t: t.peers_sending_to_us),
        SortOrder('leechers', 'Leechers', 'l', 'L',
                  lambda t: t.peers_getting_from_us),
        ]


# Common screens


class AddTorrentDialog(ModalScreen):

    def __init__(self, session):
        self.session = session
        super().__init__()

    def compose(self) -> ComposeResult:
        yield AddTorrentWidget(self.session)


class AddTorrentWidget(Static):

    r_download_dir = reactive('')

    BINDINGS = [
            Binding("enter", "add", "[Torrent] Add torrent", priority=True),
            Binding("escape", "close", "[Torrent] Close"),
            ]

    def __init__(self, session):
        self.session = session
        super().__init__()

    def compose(self) -> ComposeResult:
        yield ReactiveLabel().data_bind(
                name=AddTorrentWidget.r_download_dir)
        yield TextArea()

    def on_mount(self) -> None:
        self.border_title = 'Add torrent (local file, magnet link, URL)'
        self.border_subtitle = '(Enter) Add / (ESC) Close'

        free_space = print_size(self.session.download_dir_free_space)
        download_dir = self.session.download_dir

        self.r_download_dir = f'Destination folder: {download_dir} ({free_space} Free)'

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
                if self.is_link(text):
                    return text
        except pyperclip.PyperclipException:
            return None

        return None

    def is_link(self, text) -> bool:
        text = text.strip()
        return text.startswith(tuple(['magnet:', 'http://', 'https://']))

    def action_add(self) -> None:
        value = self.query_one(TextArea).text

        self.post_message(MainApp.AddTorrent(value, self.is_link(value)))
        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)


class UpdateTorrentLabelsDialog(ModalScreen):

    def __init__(self, torrent, torrent_ids):
        self.torrent = torrent
        self.torrent_ids = torrent_ids
        super().__init__()

    def compose(self) -> ComposeResult:
        yield UpdateTorrentLabelsWidget(self.torrent, self.torrent_ids)


class UpdateTorrentLabelsWidget(Static):

    BINDINGS = [
            Binding("enter", "update", "[Torrent] Update labels", priority=True),
            Binding("escape", "close", "[Torrent] Close"),
            ]

    def __init__(self, torrent, torrent_ids):
        self.torrent = torrent
        self.torrent_ids = torrent_ids
        super().__init__()

    def compose(self) -> ComposeResult:
        yield TextArea()

    def on_mount(self) -> None:
        self.border_title = 'Update torrent labels (comma-separated list)'
        self.border_subtitle = '(Enter) Update / (ESC) Close'

        text_area = self.query_one(TextArea)

        if self.torrent and len(self.torrent.labels) > 0:
            text_area.load_text(", ".join(self.torrent.labels))

        text_area.cursor_location = text_area.document.end

    def action_update(self) -> None:
        value = self.query_one(TextArea).text

        if self.torrent:
            torrent_ids = [self.torrent.id]
        else:
            torrent_ids = self.torrent_ids

        self.post_message(MainApp.TorrentLabelsUpdated(
            torrent_ids, value))

        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)


class SearchDialog(ModalScreen):

    def compose(self) -> ComposeResult:
        yield SearchWidget()


class SearchWidget(Static):

    BINDINGS = [
            Binding("enter", "search", "[Search] Search", priority=True),
            Binding("escape", "close", "[Search] Close"),
    ]

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Enter search term...", id="search-input")

    def on_mount(self) -> None:
        self.border_title = 'Search'
        self.border_subtitle = '(Enter) Search / (ESC) Close'
        self.query_one("#search-input").focus()

    def action_search(self) -> None:
        value = self.query_one("#search-input").value

        self.post_message(MainApp.SearchTorrent(value))
        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)


class SortOrderDialog(ModalScreen):

    def compose(self) -> ComposeResult:
        yield SortOrderWidget()


class SortOrderWidget(Static):

    BINDINGS = [
            Binding("escape,x", "close", "[Navigation] Close"),
            ]

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none",
                        zebra_stripes=True)

    def on_mount(self) -> None:
        self.border_title = 'Sort order'
        self.border_subtitle = '(X) Close'

        table = self.query_one(DataTable)
        table.add_columns("Order", "Key (ASC | DESC)")

        for o in sort_orders:
            table.add_row(o.name,
                          Text(str(f'   {o.key_asc} | {o.key_desc}'), justify="center"))

            b = Binding(o.key_asc, f"select_order('{o.id}', True)")
            self._bindings._add_binding(b)

            b = Binding(o.key_desc, f"select_order('{o.id}', False)")
            self._bindings._add_binding(b)

    def action_select_order(self, sort_id, is_asc):
        order = next(x for x in sort_orders if x.id == sort_id)

        self.post_message(MainApp.SortOrderSelected(order, is_asc))

        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)


class PreferencesDialog(ModalScreen):

    BINDINGS = [
            Binding("k", "scroll_up", "[Navigation] Scroll up"),
            Binding("j", "scroll_down", "[Navigation] Scroll down"),

            Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
            Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),

            Binding("x,escape", "close", "[Navigation] Close"),
            ]

    def __init__(self, session):
        self.session = session
        super().__init__()

    def compose(self) -> ComposeResult:
        yield PreferencesWidget(self.session)

    def action_scroll_up(self) -> None:
        self.query_one(DataTable).scroll_up()

    def action_scroll_down(self) -> None:
        self.query_one(DataTable).scroll_down()

    def action_scroll_top(self) -> None:
        self.query_one(DataTable).scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one(DataTable).scroll_end()

    def action_close(self) -> None:
        self.dismiss(False)


class PreferencesWidget(Static):

    def __init__(self, session):
        self.session = session
        super().__init__()

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none",
                        zebra_stripes=True)

    def on_mount(self) -> None:
        self.border_title = 'Transmission Preferences'
        self.border_subtitle = '(X) Close'

        table = self.query_one(DataTable)
        table.add_columns("Name", "Value")

        # Get all session attributes
        session_dict = self.session.fields

        # Sort keys for consistent display
        for key in sorted(session_dict.keys()):
            # Skip certain preferences
            if key.startswith(tuple(['units', 'version'])):
                continue

            table.add_row(key, session_dict[key])


# Core UI panels


class TorrentListPanel(ScrollableContainer):

    class TorrentViewed(Message):

        def __init__(self, torrent) -> None:
            super().__init__()
            self.torrent = torrent

    BINDINGS = [
            Binding("k,up", "move_up", "[Navigation] Move up"),
            Binding("j,down", "move_down", "[Navigation] Move down"),

            Binding("g", "move_top", "[Navigation] Go to first item"),
            Binding("home", "move_top", "[Navigation] Go to first item"),
            Binding("G", "move_bottom", "[Navigation] Go to last item"),
            Binding("end", "move_bottom", "[Navigation] Go to last item"),

            Binding("enter,l", "view_info", "[Navigation] View info"),

            Binding("space", "toggle_mark", "[Selection] Toggle mark"),
            Binding("escape", "clear_marks", "[Selection] Clear marks"),

            Binding("a", "add_torrent", "[Torrent] Add"),
            Binding("L", "update_torrent_labels", "[Torrent] Update labels"),
            Binding("s", "sort_order", "[Torrent] Sort order"),
            Binding("P", "preferences", "[App] Preferences"),

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

    selected_item = reactive(None)

    # Multi-selection state
    marked_torrent_ids = []

    # Search state
    search_term = ""
    search_active = False

    @log_time
    def __init__(self, id: str, view_mode: str, page_size: str):
        self.view_mode = view_mode
        self.page_size = page_size
        super().__init__(id=id)

    def torrent_idx(self, torrent) -> int:
        return next((idx for idx, t in enumerate(self.r_torrents) if t.id == torrent.id), None)

    def has_prev(self, torrent) -> bool:
        idx = self.torrent_idx(torrent)

        if idx > 0:
            return True
        else:
            return False

    def has_next(self, torrent) -> bool:
        idx = self.torrent_idx(torrent)

        if idx >= (len(self.r_torrents) - 1):
            return False
        else:
            return True

    def total_pages(self, torrents) -> int:
        if len(torrents) == 0:
            pages = 0
        else:
            pages = math.ceil(len(torrents) / self.page_size)

        return pages

    @log_time
    def watch_r_torrents(self, new_r_torrents):
        if new_r_torrents:
            torrents = new_r_torrents

            # Clean up marked torrents list - remove IDs not present in new torrent list
            current_torrent_ids = {t.id for t in torrents}
            self.marked_torrent_ids = [tid for tid in self.marked_torrent_ids
                                       if tid in current_torrent_ids]

            # detect current page by selected item

            if self.selected_item:
                selected_idx = self.torrent_idx(self.selected_item.torrent)

                if selected_idx is not None:
                    current_page = selected_idx // self.page_size
                else:
                    # if during torrents update selected torrent was not found,
                    # then remove its selection
                    self.selected_item = None
                    current_page = 0
            else:
                current_page = 0

            self.update_page(torrents, current_page * self.page_size)

    @log_time
    async def watch_selected_item(self, new_selected_item):
        if new_selected_item:
            self.scroll_to_widget(new_selected_item)
        else:
            self.scroll_home()

    @log_time
    def update_page(self,
                    torrents, start_index=None,
                    select_first=False, select_last=False, force=False):

        if start_index is None:
            start_index = self.torrent_idx(self.children[0].torrent)

        page_torrents = torrents[start_index:start_index + self.page_size]

        if not force and self.is_equal_to_page(page_torrents):
            torrent_widgets = self.children

            for i, torrent in enumerate(page_torrents):
                torrent_widgets[i].update_torrent(torrent)
        else:
            torrent_widgets = self.draw_page(page_torrents, select_first, select_last)

            state = PageState(current=(start_index // self.page_size),
                              total=self.total_pages(torrents))

            self.post_message(MainApp.PageChanged(state))

        self.update_selection(torrent_widgets, select_first, select_last)

    def update_selection(self, torrent_widgets, select_first, select_last) -> None:
        prev_selected_item = self.selected_item

        if select_first:
            self.selected_item = torrent_widgets[0]
            self.selected_item.selected = True

            if prev_selected_item and prev_selected_item is not self.selected_item:
                prev_selected_item.selected = False
        elif select_last:
            self.selected_item = torrent_widgets[-1]
            self.selected_item.selected = True

            if prev_selected_item and prev_selected_item is not self.selected_item:
                prev_selected_item.selected = False
        else:
            if self.selected_item:
                prev_selected_id = self.selected_item.torrent.id

                for item in torrent_widgets:
                    if prev_selected_id == item.torrent.id:
                        item.selected = True
                        self.selected_item = item

        # Update marked state for all items
        for item in torrent_widgets:
            item.marked = item.torrent.id in self.marked_torrent_ids

    @log_time
    def create_item(self, torrent) -> TorrentItem:
        if self.view_mode == 'card':
            item = TorrentItemCard(torrent)
        elif self.view_mode == 'compact':
            item = TorrentItemCompact(torrent)
        elif self.view_mode == 'oneline':
            item = TorrentItemOneline(torrent)

        return item

    @log_time
    def draw_page(self, torrents, select_first=False, select_last=False):
        self.remove_children()

        torrent_widgets = []

        w_prev = None
        for t in torrents:
            item = self.create_item(t)

            torrent_widgets.append(item)

            if w_prev:
                w_prev.w_next = item
                item.w_prev = w_prev
                w_prev = item
            else:
                w_prev = item

        self.mount_all(torrent_widgets)

        return torrent_widgets

    @log_time
    def is_equal_to_page(self, torrents) -> bool:
        items = self.children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i].t_id:
                return False

        return True

    @log_time
    def action_move_up(self) -> None:
        items = self.children

        if items:
            if self.selected_item is None:
                item = items[-1]
                item.selected = True
                self.selected_item = item
            else:
                if self.selected_item.w_prev:
                    self.selected_item.selected = False
                    self.selected_item = self.selected_item.w_prev
                    self.selected_item.selected = True
                else:
                    # has item on the prev page?
                    if self.has_prev(self.selected_item.torrent):
                        page_start_idx = self.torrent_idx(self.selected_item.torrent) - self.page_size
                        self.update_page(self.r_torrents, page_start_idx, select_last=True)

    @log_time
    def action_move_down(self) -> None:
        items = self.children

        if items:
            if self.selected_item is None:
                item = items[0]
                item.selected = True
                self.selected_item = item
            else:
                if self.selected_item.w_next:
                    self.selected_item.selected = False
                    self.selected_item = self.selected_item.w_next
                    self.selected_item.selected = True
                else:
                    # has item on the next page?
                    if self.has_next(self.selected_item.torrent):
                        page_start_idx = self.torrent_idx(self.selected_item.torrent) + 1
                        self.update_page(self.r_torrents, page_start_idx, select_first=True)

    @log_time
    def action_move_top(self) -> None:
        self.update_page(self.r_torrents, 0, select_first=True)

    @log_time
    def action_move_bottom(self) -> None:
        last_page_start_idx = (self.total_pages(self.r_torrents) - 1) * self.page_size

        self.update_page(self.r_torrents, last_page_start_idx,
                         select_last=True)

    def move_to(self, selector) -> None:
        items = self.children

        if items:
            if self.selected_item:
                self.selected_item.selected = False

            self.selected_item = selector(items)
            self.selected_item.selected = True

    @log_time
    def action_toggle_mark(self) -> None:
        if self.selected_item:
            torrent_id = self.selected_item.torrent.id

            if torrent_id in self.marked_torrent_ids:
                self.marked_torrent_ids.remove(torrent_id)
                self.selected_item.marked = False
            else:
                self.marked_torrent_ids.append(torrent_id)
                self.selected_item.marked = True

            # Move to next torrent if available
            if self.selected_item.w_next:
                self.selected_item.selected = False
                self.selected_item = self.selected_item.w_next
                self.selected_item.selected = True
            elif self.has_next(self.selected_item.torrent):
                # Has item on the next page
                page_start_idx = self.torrent_idx(self.selected_item.torrent) + 1
                self.update_page(self.r_torrents, page_start_idx, select_first=True)

    @log_time
    def action_clear_marks(self) -> None:
        self.marked_torrent_ids.clear()

        # Update visual state for all currently visible items
        for item in self.children:
            item.marked = False

    @log_time
    def action_view_info(self):
        if self.selected_item:
            self.post_message(self.TorrentViewed(self.selected_item.torrent))

    @log_time
    def action_add_torrent(self) -> None:
        self.post_message(MainApp.OpenAddTorrent())

    @log_time
    def action_update_torrent_labels(self) -> None:
        if self.marked_torrent_ids:
            self.post_message(
                    MainApp.OpenUpdateTorrentLabels(
                        None,
                        self.marked_torrent_ids))
        elif self.selected_item:
            self.post_message(
                    MainApp.OpenUpdateTorrentLabels(
                        self.selected_item.torrent,
                        None))

    @log_time
    def action_sort_order(self) -> None:
        self.post_message(MainApp.OpenSortOrder())

    @log_time
    def action_preferences(self) -> None:
        self.post_message(MainApp.OpenPreferences())

    @log_time
    def action_toggle_torrent(self) -> None:
        if not self.marked_torrent_ids:
            # No marked torrents - toggle currently selected torrent
            if self.selected_item:
                status = self.selected_item.t_status

                if status == 'stopped':
                    self.client().start_torrent(self.selected_item.t_id)
                    self.post_message(MainApp.Notification("Torrent started"))
                else:
                    self.client().stop_torrent(self.selected_item.t_id)
                    self.post_message(MainApp.Notification("Torrent stopped"))
        else:
            # There are marked torrents - toggle them based on their status
            marked_torrents = [t for t in self.r_torrents if t.id in self.marked_torrent_ids]

            # Check if at least one torrent is paused/stopped
            has_stopped = any(t.status == 'stopped' for t in marked_torrents)

            if has_stopped:
                # Start all marked torrents
                self.client().start_torrent(self.marked_torrent_ids)
                self.post_message(MainApp.Notification(f"Started {len(self.marked_torrent_ids)} marked torrents"))
            else:
                # Stop all marked torrents
                self.client().stop_torrent(self.marked_torrent_ids)
                self.post_message(MainApp.Notification(f"Stopped {len(self.marked_torrent_ids)} marked torrents"))

    @log_time
    def action_remove_torrent(self) -> None:
        if self.marked_torrent_ids:
            count = len(self.marked_torrent_ids)
            torrent_word = "torrent" if count == 1 else "torrents"
            file_word = "file" if count == 1 else "files"
            pronoun = "it" if count == 1 else "them"
            message = f"Remove {count} marked {torrent_word}?"
            description = ("Once removed, continuing the "
                           f"transfer will require the torrent {file_word}. "
                           f"Are you sure you want to remove {pronoun}?")
            notification = f"{count} marked {torrent_word} removed"

            self.remove_marked_torrent(delete_data=False,
                                       message=message,
                                       description=description,
                                       notification=notification)
        else:
            message = "Remove torrent?"
            description = ("Once removed, continuing the "
                           "transfer will require the torrent file. "
                           "Are you sure you want to remove it?")
            notification = "Torrent removed"

            self.remove_selected_torrent(delete_data=False,
                                         message=message,
                                         description=description,
                                         notification=notification)

    @log_time
    def action_trash_torrent(self) -> None:
        if self.marked_torrent_ids:
            count = len(self.marked_torrent_ids)
            torrent_word = "torrent" if count == 1 else "torrents"
            pronoun_these = "this" if count == 1 else "these"
            pronoun_it = "it" if count == 1 else "them"
            data_word = "its" if count == 1 else "their"
            message = f"Remove {count} marked {torrent_word} and delete data?"
            description = (f"All data downloaded for {pronoun_these} {count} {torrent_word} "
                           "will be deleted. Are you sure you "
                           f"want to remove {pronoun_it}?")
            notification = f"{count} marked {torrent_word} and {data_word} data removed"

            self.remove_marked_torrent(delete_data=True,
                                       message=message,
                                       description=description,
                                       notification=notification)
        else:
            message = "Remove torrent and delete data?"
            description = ("All data downloaded for this torrent "
                           "will be deleted. Are you sure you "
                           "want to remove it?")
            notification = "Torrent and its data removed"

            self.remove_selected_torrent(delete_data=True,
                                         message=message,
                                         description=description,
                                         notification=notification)

    @log_time
    def remove_marked_torrent(self,
                              delete_data: bool,
                              message: str,
                              description: str,
                              notification: str) -> None:

        if self.marked_torrent_ids:

            def check_quit(confirmed: bool | None) -> None:
                if confirmed:
                    self.client().remove_torrent(self.marked_torrent_ids,
                                                 delete_data=delete_data)

                    # TODO: remove torrents from items list

                    self.post_message(MainApp.Notification(notification))

            self.post_message(MainApp.Confirm(message=message,
                                              description=description,
                                              check_quit=check_quit))

    @log_time
    def remove_selected_torrent(self,
                                delete_data: bool,
                                message: str,
                                description: str,
                                notification: str) -> None:

        if self.selected_item:

            def check_quit(confirmed: bool | None) -> None:
                if confirmed:
                    self.client().remove_torrent(self.selected_item.t_id,
                                                 delete_data=delete_data)

                    w_prev = self.selected_item.w_prev
                    w_next = self.selected_item.w_next

                    self.r_torrents.remove(self.selected_item.torrent)
                    self.selected_item.remove()

                    if w_next:
                        w_next.w_prev = w_prev

                    if w_prev:
                        w_prev.w_next = w_next

                    new_selected = None
                    if w_next:
                        new_selected = w_next
                    elif w_prev:
                        new_selected = w_prev

                    if new_selected:
                        new_selected.selected = True
                        self.selected_item = new_selected
                        self.scroll_to_widget(self.selected_item)
                    else:
                        self.selected_item = None

                    self.post_message(MainApp.Notification(notification))

            self.post_message(MainApp.Confirm(message=message,
                                              description=description,
                                              check_quit=check_quit))

    @log_time
    def action_verify_torrent(self) -> None:
        if not self.marked_torrent_ids:
            # No marked torrents - verify currently selected torrent
            if self.selected_item:
                self.client().verify_torrent(self.selected_item.t_id)
                self.post_message(MainApp.Notification("Torrent sent to verification"))
        else:
            # There are marked torrents - verify them all
            self.client().verify_torrent(self.marked_torrent_ids)
            self.post_message(MainApp.Notification(
                f"Sent {len(self.marked_torrent_ids)} marked torrents to verification"))

    @log_time
    def action_reannounce_torrent(self) -> None:
        if not self.marked_torrent_ids:
            # No marked torrents - reannounce currently selected torrent
            if self.selected_item:
                self.client().reannounce_torrent(self.selected_item.t_id)
                self.post_message(MainApp.Notification("Torrent reannounce started"))
        else:
            # There are marked torrents - reannounce them all
            self.client().reannounce_torrent(self.marked_torrent_ids)
            self.post_message(MainApp.Notification(
                f"Reannounce started for {len(self.marked_torrent_ids)} marked torrents"))

    @log_time
    def action_start_all_torrents(self) -> None:
        self.client().start_all()
        self.post_message(MainApp.Notification("All torrents started"))

    @log_time
    def action_stop_all_torrents(self) -> None:
        self.client().stop_torrent([t.id for t in self.r_torrents])
        self.post_message(MainApp.Notification("All torrents stopped"))

    @log_time
    def action_toggle_view_mode(self) -> None:
        if self.view_mode == 'card':
            self.view_mode = 'compact'
        elif self.view_mode == 'compact':
            self.view_mode = 'oneline'
        elif self.view_mode == 'oneline':
            self.view_mode = 'card'

        self.update_page(self.r_torrents, force=True)

    @log_time
    def action_search(self) -> None:
        # Reset search state when opening search dialog
        self.search_active = False
        self.search_term = ""
        self.post_message(MainApp.OpenSearch())

    @log_time
    def action_search_next(self) -> None:
        if not self.search_active or not self.search_term:
            self.post_message(MainApp.Notification("No active search"))
            return

        self._search_torrent(self.search_term, forward=True)

    @log_time
    def action_search_previous(self) -> None:
        if not self.search_active or not self.search_term:
            self.post_message(MainApp.Notification("No active search"))
            return

        self._search_torrent(self.search_term, forward=False)

    @log_time
    def _search_torrent(self, search_term: str, forward: bool = True) -> None:
        if not search_term or not self.r_torrents:
            return

        search_term = search_term.lower()

        # Get current index if there's a selected item
        current_idx = -1
        if self.selected_item:
            current_idx = self.torrent_idx(self.selected_item.torrent)

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
        self.post_message(MainApp.Notification(f"No torrents matching '{search_term}'"))

    @log_time
    def _select_found_torrent(self, index: int) -> None:
        # Calculate page start index
        page_start_idx = (index // self.page_size) * self.page_size

        # Update page to show the found torrent
        self.update_page(self.r_torrents, page_start_idx)

        # Select the found item
        for item in self.children:
            if item.torrent.id == self.r_torrents[index].id:
                if self.selected_item:
                    self.selected_item.selected = False
                item.selected = True
                self.selected_item = item
                self.scroll_to_widget(item)
                return

    @log_time
    def search_torrent(self, search_term: str) -> None:
        if search_term:
            self.search_term = search_term
            self.search_active = True
            self._search_torrent(search_term, forward=True)

    @log_time
    def client(self):
        # TODO: get client
        return self.parent.parent.parent.parent.client


class MainApp(App):

    class Notification(Message):

        def __init__(self,
                     message: str,
                     severity: str = 'information'):

            super().__init__()
            self.message = message
            self.severity = severity

    class Confirm(Message):
        def __init__(self, message, description, check_quit):
            super().__init__()
            self.message = message
            self.description = description
            self.check_quit = check_quit

    class OpenAddTorrent(Message):
        pass

    class OpenUpdateTorrentLabels(Message):
        def __init__(self, torrent, torrent_ids):
            super().__init__()
            self.torrent = torrent
            self.torrent_ids = torrent_ids

    class OpenSortOrder(Message):
        pass

    class AddTorrent(Message):
        def __init__(self, value: str, is_link: bool) -> None:
            super().__init__()
            self.value = value
            self.is_link = is_link

    class SearchTorrent(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    class TorrentLabelsUpdated(Message):
        def __init__(self, torrent_ids, value: str) -> None:
            super().__init__()
            self.torrent_ids = torrent_ids
            self.value = value

    class SortOrderSelected(Message):
        def __init__(self, order: str, is_asc: bool) -> None:
            super().__init__()
            self.order = order
            self.is_asc = is_asc

    class OpenSearch(Message):
        pass

    class OpenPreferences(Message):
        pass

    class PageChanged(Message):
        def __init__(self, state: PageState) -> None:
            super().__init__()
            self.state = state

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("t", "toggle_alt_speed", "[Speed] Toggle limits"),
            Binding("S", "show_statistics", "[Info] Statistics"),

            Binding('"', "screenshot", "[App] Screenshot"),

            Binding("d", "toggle_dark", "[UI] Toggle theme", priority=True),
            Binding("?", "help", "[App] Help"),
            Binding("q", "quit", "[App] Quit", priority=True),
            ]

    r_torrents = reactive(None)
    r_tsession = reactive(None)
    r_page = reactive(None)

    @log_time
    def __init__(self, host: str, port: str,
                 username: str, password: str,
                 view_mode: str,
                 refresh_interval: int,
                 page_size: int,
                 limit_torrents: int,
                 version: str):

        super().__init__()

        self.title = 'Tewi'

        self.view_mode = view_mode
        self.refresh_interval = refresh_interval
        self.limit_torrents = limit_torrents
        self.page_size = page_size

        self.tewi_version = version

        self.c_host = host
        self.c_port = port

        self.client = Client(host=self.c_host, port=self.c_port,
                             username=username, password=password)

        self.transmission_version = self.client.get_session().version

        self.sort_order = sort_orders[0]
        self.sort_order_asc = True

    @log_time
    def compose(self) -> ComposeResult:
        yield InfoPanel(self.tewi_version, self.transmission_version,
                        self.c_host, self.c_port)

        with Horizontal():
            with ContentSwitcher(initial="torrent-list"):
                yield TorrentListPanel(id="torrent-list",
                                       view_mode=self.view_mode,
                                       page_size=self.page_size).data_bind(
                                               r_torrents=MainApp.r_torrents)
                yield TorrentInfoPanel(id="torrent-info")

        yield StatePanel().data_bind(r_tsession=MainApp.r_tsession,
                                     r_page=MainApp.r_page)

    @log_time
    def on_mount(self) -> None:
        self.load_tdata()
        self.set_interval(self.refresh_interval, self.load_tdata)

    @log_time
    @work(exclusive=True, thread=True)
    async def load_tdata(self) -> None:
        logging.info("Start loading data from Transmission...")

        session = self.client.get_session()
        session_stats = self.client.session_stats()
        torrents = self.client.get_torrents()

        if self.limit_torrents:
            torrents = torrents[:self.limit_torrents]

        torrents_down = len([x for x in torrents if x.status == 'downloading'])
        torrents_seed = len([x for x in torrents if x.status == 'seeding'])
        torrents_check = len([x for x in torrents if x.status == 'checking'])
        torrents_stop = len(torrents) - torrents_down - torrents_seed - torrents_check

        torrents_complete_size = sum(t.size_when_done - t.left_until_done for t in torrents)
        torrents_total_size = sum(t.size_when_done for t in torrents)

        tsession = TransmissionSession(
                session=session,
                session_stats=session_stats,
                torrents_down=torrents_down,
                torrents_seed=torrents_seed,
                torrents_check=torrents_check,
                torrents_stop=torrents_stop,
                torrents_complete_size=torrents_complete_size,
                torrents_total_size=torrents_total_size,
                sort_order=self.sort_order,
                sort_order_asc=self.sort_order_asc,
                )

        torrents.sort(key=self.sort_order.sort_func,
                      reverse=not self.sort_order_asc)

        self.log(vars(session))
        self.log(vars(session_stats))

        logging.info(f"Loaded from Transmission {session.version}: {len(torrents)} torrents")

        self.call_from_thread(self.set_tdata, torrents, tsession)

    @log_time
    def set_tdata(self, torrents, tsession) -> None:
        self.r_torrents = torrents
        self.r_tsession = tsession

    @log_time
    def action_toggle_alt_speed(self) -> None:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled=not alt_speed_enabled)

        if alt_speed_enabled:
            self.post_message(MainApp.Notification("Turtle Mode disabled"))
        else:
            self.post_message(MainApp.Notification("Turtle Mode enabled"))

    @log_time
    def action_show_statistics(self) -> None:
        self.push_screen(StatisticsDialog(self.r_tsession.session_stats))

    @log_time
    def action_help(self) -> None:
        self.push_screen(HelpDialog(self.screen.active_bindings.values()))

    @log_time
    @on(TorrentListPanel.TorrentViewed)
    def handle_torrent_view(self, event: TorrentListPanel.TorrentViewed) -> None:
        self.query_one(ContentSwitcher).current = "torrent-info"
        self.query_one(TorrentInfoPanel).r_torrent = event.torrent

    @log_time
    @on(TorrentInfoPanel.TorrentViewClosed)
    def handle_torrent_list(self, event: TorrentInfoPanel.TorrentViewClosed) -> None:
        self.query_one(ContentSwitcher).current = "torrent-list"

    @log_time
    @on(Notification)
    def handle_notification(self, event: Notification) -> None:
        timeout = 3 if event.severity == 'information' else 5

        self.notify(message=event.message,
                    severity=event.severity,
                    timeout=timeout)

    @log_time
    @on(Confirm)
    def handle_confirm(self, event: Confirm) -> None:
        self.push_screen(
                    ConfirmDialog(message=event.message,
                                  description=event.description),
                    event.check_quit)

    @log_time
    @on(OpenAddTorrent)
    def handle_open_add_torrent(self, event: OpenAddTorrent) -> None:
        self.push_screen(AddTorrentDialog(self.r_tsession.session))

    @log_time
    @on(OpenUpdateTorrentLabels)
    def handle_open_update_torrent_labels(self, event: OpenUpdateTorrentLabels) -> None:
        self.push_screen(UpdateTorrentLabelsDialog(event.torrent, event.torrent_ids))

    @log_time
    @on(OpenSortOrder)
    def handle_open_sort_order(self, event: OpenSortOrder) -> None:
        self.push_screen(SortOrderDialog())

    @log_time
    @on(OpenPreferences)
    def handle_open_preferences(self, event: OpenPreferences) -> None:
        self.push_screen(PreferencesDialog(self.r_tsession.session))

    @log_time
    @on(OpenSearch)
    def handle_open_search(self, event: OpenSearch) -> None:
        self.push_screen(SearchDialog())

    @log_time
    @on(AddTorrent)
    def handle_add_torrent(self, event: AddTorrent) -> None:
        try:
            if event.is_link:
                self.client.add_torrent(event.value)
            else:
                file = os.path.expanduser(event.value)
                self.client.add_torrent(pathlib.Path(file))

            self.post_message(MainApp.Notification("New torrent was added"))
        except TransmissionError as e:
            self.post_message(MainApp.Notification(
                f"Failed to add torrent:\n{e}",
                "warning"))
        except FileNotFoundError:
            self.post_message(MainApp.Notification(
                f"Failed to add torrent:\nFile not found {file}",
                "warning"))

    @log_time
    @on(SearchTorrent)
    def handle_search_torrent(self, event: SearchTorrent) -> None:
        self.query_one(TorrentListPanel).search_torrent(event.value)

    @log_time
    @on(TorrentLabelsUpdated)
    def handle_torrent_labels_updated(self, event: TorrentLabelsUpdated) -> None:
        labels = [x.strip() for x in event.value.split(',') if x.strip()]

        if len(event.torrent_ids) == 1:
            count_label = '1 torrent'
        else:
            count_label = f"{len(event.torrent_ids)} torrents"

        if len(labels) > 0:
            self.client.change_torrent(event.torrent_ids,
                                       labels=labels)

            self.post_message(MainApp.Notification(
                f"Updated torrent labels ({count_label}):\n{','.join(labels)}"))
        else:
            self.client.change_torrent(event.torrent_ids,
                                       labels=[])
            self.post_message(MainApp.Notification(
                "Removed torrent labels ({count_label})"))

    @log_time
    @on(SortOrderSelected)
    def handle_sort_order_selected(self, event: SortOrderSelected) -> None:
        self.sort_order = event.order
        self.sort_order_asc = event.is_asc

        direction = 'ASC' if event.is_asc else 'DESC'
        self.post_message(MainApp.Notification(
            f"Selected sort order: {event.order.name} {direction}"))

    @log_time
    @on(PageChanged)
    def handle_page_changed(self, event: PageChanged) -> None:
        self.r_page = event.state


def cli():
    tewi_version = __version__

    parser = argparse.ArgumentParser(
            prog='tewi',
            description='Text-based interface for the Transmission BitTorrent daemon',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--view-mode', type=str, default='card',
                        choices=['card', 'compact', 'oneline'],
                        help='View mode for torrents in list')
    parser.add_argument('--refresh-interval', type=int, default=5,
                        help='Refresh interval (in seconds) for loading data from Transmission daemon')
    parser.add_argument('--limit-torrents', type=int, default=None,
                        help='Limit number of displayed torrents (useful for performance debugging)')
    parser.add_argument('--page-size', type=int, default=50,
                        help='Number of torrents displayed per page')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Transmission daemon host for connection')
    parser.add_argument('--port', type=str, default='9091',
                        help='Transmission daemon port for connection')
    parser.add_argument('--username', type=str,
                        help='Transmission daemon username for connection')
    parser.add_argument('--password', type=str,
                        help='Transmission daemon password for connection')
    parser.add_argument('--logs', default=False,
                        action=argparse.BooleanOptionalAction,
                        help='Enable verbose logs (added to `tewi.log` file)')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + tewi_version,
                        help='Show version and exit')

    args = parser.parse_args()

    if args.logs:
        logging.basicConfig(
                filename=('tewi.log'),
                encoding='utf-8',
                format='%(asctime)s.%(msecs)03d %(module)-15s %(levelname)-8s %(message)s',
                level=logging.DEBUG,
                datefmt='%Y-%m-%d %H:%M:%S')

    logger.info(f'Start Tewi {tewi_version}...')
    logger.info(f'Loaded CLI options: {args}')

    try:
        app = MainApp(host=args.host, port=args.port,
                      username=args.username, password=args.password,
                      view_mode=args.view_mode,
                      refresh_interval=args.refresh_interval,
                      page_size=args.page_size,
                      limit_torrents=args.limit_torrents,
                      version=tewi_version)
        app.run()
        return app
    except TransmissionError as e:
        print(f"Failed to connect to Transmission daemon at {args.host}:{args.port}: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize application: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
