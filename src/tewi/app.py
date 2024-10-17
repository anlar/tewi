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

import argparse
import textwrap
from datetime import datetime

from transmission_rpc import Client

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, ScrollableContainer, Horizontal, Container
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static, Label, ProgressBar, DataTable, ContentSwitcher, TabbedContent, TabPane


# Common data

class TransmissionData:
    def __init__(self, session, session_stats, torrents):
        self.session = session
        self.session_stats = session_stats
        self.torrents = torrents


# Common utils

class Util:

    def print_size(num: int,
                   suffix: str = "B", size_bytes: int = 1000):

        r_unit = None
        r_num = None

        for unit in ("", "k", "M", "G", "T", "P", "E", "Z", "Y"):
            if abs(num) < size_bytes:
                r_unit = unit
                r_num = num
                break
            num /= size_bytes

        round(r_num, 2)

        r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

        return f"{r_size} {r_unit}{suffix}"

    def print_speed(num: int,
                    print_secs: bool = False,
                    suffix: str = "B",
                    speed_bytes: int = 1000) -> str:

        r_unit = None
        r_num = None

        for i in (("", 0), ("K", 0), ("M", 2), ("G", 2), ("T", 2), ("P", 2), ("E", 2), ("Z", 2), ("Y", 2)):

            if abs(num) < speed_bytes:
                r_unit = i[0]
                r_num = round(num, i[1])
                break
            num /= speed_bytes

        r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

        if print_secs:
            return f"{r_size} {r_unit}{suffix}/s"
        else:
            return f"{r_size} {r_unit}{suffix}"


# Common UI components

class ReactiveLabel(Label):

    name = reactive(None)

    def render(self):
        return self.name


# Common torrent-related widgets

class SpeedIndicator(Static):

    speed = reactive(0)

    def render(self) -> str:
        return Util.print_speed(self.speed)


# Common screens

class ConfirmationDialog(ModalScreen):

    BINDINGS = [
            Binding("y", "confirm", "Yes"),
            Binding("n,x,escape", "close", "No"),
            ]

    def __init__(self, message: str, description: str = None) -> None:
        self.message = message
        self.description = description
        super().__init__()

    def compose(self) -> ComposeResult:
        yield ConfirmationWidget(self.message, self.description)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_close(self) -> None:
        self.dismiss(False)


class ConfirmationWidget(Static):

    def __init__(self, message: str, description: str = None) -> None:
        self.message = message
        self.description = description
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(self.message)

        if self.description:
            # empty space between message and description
            yield Label('')
            for line in textwrap.wrap(self.description, 56):
                yield Label(line)

    def on_mount(self):
        self.border_title = 'Confirmation'
        self.border_subtitle = '[Y] Yes / [N] No'


class HelpDialog(ModalScreen):

    BINDINGS = [
            Binding("x,escape", "close", "Close"),
            ]

    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__()

    def compose(self) -> ComposeResult:
        yield HelpWidget(self.bindings)

    def action_close(self) -> None:
        self.dismiss(False)


class HelpWidget(Static):

    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield DataTable(cursor_type="none",
                            zebra_stripes=True)

    def on_mount(self) -> None:
        self.border_title = 'Help'
        self.border_subtitle = '[X] Close'

        table = self.query_one(DataTable)
        table.add_columns("Key", "Command")

        for b in filter(lambda x: x.binding.show, self.bindings):
            key = b.binding.key

            if key == 'question_mark':
                key = '?'

            if len(key) > 1:
                key = key.title()

            table.add_row(key, b.binding.description)


class StatisticsDialog(ModalScreen):

    BINDINGS = [
            Binding("x,escape", "close", "Close"),
            ]

    def __init__(self, session_stats) -> None:
        self.session_stats = session_stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield StatisticsWidget(self.session_stats)

    def action_close(self) -> None:
        self.dismiss(False)


class StatisticsWidget(Static):

    r_upload = reactive("")
    r_download = reactive("")
    r_ratio = reactive("")
    r_time = reactive("")

    r_total_upload = reactive("")
    r_total_download = reactive("")
    r_total_ratio = reactive("")
    r_total_time = reactive("")
    r_total_started = reactive("")

    def __init__(self, session_stats) -> None:
        self.session_stats = session_stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("Current Session", classes="title")
        yield Static("  Uploaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_upload)
        yield Static("  Downloaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_download)
        yield Static("  Ratio:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_ratio)
        yield Static("  Running Time:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_time)
        yield Static(" ", classes="title")
        yield Static("Total", classes="title")
        yield Static("  Uploaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_upload)
        yield Static("  Downloaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_download)
        yield Static("  Ratio:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_ratio)
        yield Static("  Running Time:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_time)
        yield Static("  Started:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_total_started)

    def on_mount(self) -> None:
        self.border_title = 'Statistics'
        self.border_subtitle = '[X] Close'

        # current stats

        self.r_upload = Util.print_size(self.session_stats.current_stats.uploaded_bytes)
        self.r_download = Util.print_size(self.session_stats.current_stats.downloaded_bytes)

        self.r_ratio = self.print_ratio(self.session_stats.current_stats.uploaded_bytes,
                                        self.session_stats.current_stats.downloaded_bytes)

        self.r_time = self.print_time(self.session_stats.current_stats.seconds_active)

        # cumulative stats

        self.r_total_upload = Util.print_size(self.session_stats.cumulative_stats.uploaded_bytes)
        self.r_total_download = Util.print_size(self.session_stats.cumulative_stats.downloaded_bytes)

        self.r_total_ratio = self.print_ratio(self.session_stats.cumulative_stats.uploaded_bytes,
                                              self.session_stats.cumulative_stats.downloaded_bytes)

        self.r_total_time = self.print_time(self.session_stats.cumulative_stats.seconds_active)
        self.r_total_started = f"{self.session_stats.cumulative_stats.session_count} times"

    def print_ratio(self, uploaded, downloaded) -> str:
        if downloaded == 0:
            return "∞"

        ratio = uploaded / downloaded

        return f"{ratio:.2f}"

    def print_time(self, seconds) -> str:
        intervals = (
                ('days', 86400),    # 60 * 60 * 24
                ('hours', 3600),    # 60 * 60
                ('minutes', 60),
                ('seconds', 1),
                )
        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(value, name))
        return ', '.join(result[:1])


# Core UI panels

class InfoPanel(Static):

    def __init__(self,
                 w_version: str, w_trans_version: str,
                 w_host: str, w_port: str):

        self.w_version = w_version
        self.w_trans_version = w_trans_version
        self.w_host = w_host
        self.w_port = w_port

        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal(id="info-panel"):
            yield Static(f'Tewi {self.w_version}', classes='column')
            yield Static('»»»', classes='column delimiter')
            yield Static(f'Transmission {self.w_trans_version}', classes='column')
            yield Static('»»»', classes='column delimiter')
            yield Static(f'{self.w_host}:{self.w_port}', classes='column')
            yield Static('', classes='column space')
            yield Static('?: Help', classes='column')
            yield Static('', classes='column')
            yield Static('Q: Quit', classes='column')


class StatePanel(Static):

    r_tdata = reactive(None)

    # recompose whole line to update blocks width
    r_stats = reactive(None, recompose=True)
    r_alt_speed = reactive(None, recompose=True)
    r_alt_delimiter = reactive(None, recompose=True)

    r_upload_speed = reactive(None)
    r_download_speed = reactive(None)

    def compose(self) -> ComposeResult:
        with Grid(id="state-panel"):
            yield ReactiveLabel(classes="column").data_bind(
                    name=StatePanel.r_stats)
            yield Static("", classes="column")
            yield ReactiveLabel(classes="column alt-speed").data_bind(
                    name=StatePanel.r_alt_speed)
            yield ReactiveLabel(classes="column delimiter").data_bind(
                    name=StatePanel.r_alt_delimiter)
            yield Static("↑", classes="column arrow")
            yield SpeedIndicator(classes="column").data_bind(
                    speed=StatePanel.r_upload_speed)
            yield Static("↓", classes="column arrow")
            yield SpeedIndicator(classes="column").data_bind(
                    speed=StatePanel.r_download_speed)

    def watch_r_tdata(self, new_r_tdata):
        if new_r_tdata:
            session = new_r_tdata.session
            session_stats = new_r_tdata.session_stats
            torrents = new_r_tdata.torrents

            torrents_down = len([x for x in torrents if x.status == 'downloading'])
            torrents_seed = len([x for x in torrents if x.status == 'seeding'])
            torrents_stop = len(torrents) - torrents_down - torrents_seed

            self.r_stats = (f"Torrents: {len(torrents)} "
                            f"(Downloading: {torrents_down}, "
                            f"Seeding: {torrents_seed}, "
                            f"Paused: {torrents_stop})")

            self.r_upload_speed = session_stats.upload_speed
            self.r_download_speed = session_stats.download_speed

            alt_speed_enabled = session.alt_speed_enabled
            alt_speed_up = session.alt_speed_up
            alt_speed_down = session.alt_speed_down

            if alt_speed_enabled:
                self.r_alt_speed = f'Speed Limits: ↑ {alt_speed_up} KB ↓ {alt_speed_down} KB'
                self.r_alt_delimiter = '»»»'
            else:
                self.r_alt_speed = ''
                self.r_alt_delimiter = ''


class TorrentListPanel(ScrollableContainer):

    class TorrentViewed(Message):

        def __init__(self, torrent) -> None:
            super().__init__()
            self.torrent = torrent

    BINDINGS = [
            Binding("k,up", "move_up", "Move up"),
            Binding("j,down", "move_down", "Move down"),

            Binding("g", "move_top", "Go to the first item"),
            Binding("G", "move_bottom", "Go to the last item"),

            Binding("enter,l", "view_info", "View torrent info"),

            Binding("p", "toggle_torrent", "Toggle torrent"),
            Binding("r", "remove_torrent", "Remove torrent"),
            Binding("R", "trash_torrent", "Trash torrent"),
            Binding("v", "verify_torrent", "Verify torrent"),
            Binding("n", "reannounce_torrent", "Reannounce torrent"),

            Binding("m", "toggle_view_mode", "Toggle torrents view mode"),
            ]

    r_tdata = reactive(None)

    selected_item = None

    def __init__(self, id: str, view_mode: str):
        self.view_mode = view_mode
        super().__init__(id=id)

    def watch_r_tdata(self, new_r_tdata):
        if new_r_tdata:
            torrents = new_r_tdata.torrents

            if self.is_equal_to_pane(torrents):
                items = self.children

                for i, torrent in enumerate(torrents):
                    items[i].update_torrent(torrent)
            else:
                self.create_pane(torrents)

    def create_pane(self, torrents) -> None:
        if self.selected_item:
            prev_selected_id = self.selected_item.torrent.id
        else:
            prev_selected_id = None

        self.remove_children()

        self.selected_item = None

        w_prev = None
        for t in torrents:
            if self.view_mode == 'card':
                item = TorrentItemCard(t)
            elif self.view_mode == 'compact':
                item = TorrentItemCompact(t)

            self.mount(item)

            if w_prev:
                w_prev.w_next = item
                item.w_prev = w_prev
                w_prev = item
            else:
                w_prev = item

        if prev_selected_id:
            for item in self.children:
                if prev_selected_id == item.torrent.id:
                    item.selected = True
                    self.selected_item = item
                    self.scroll_to_widget(self.selected_item)
        else:
            self.scroll_home()

    def is_equal_to_pane(self, torrents) -> bool:
        items = self.children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i].t_id:
                return False

        return True

    def action_move_up(self) -> None:
        items = self.children

        if items:
            if self.selected_item is None:
                item = items[-1]
                item.selected = True
                self.selected_item = item
                self.scroll_to_widget(self.selected_item)
            else:
                if self.selected_item.w_prev:
                    self.selected_item.selected = False
                    self.selected_item = self.selected_item.w_prev
                    self.selected_item.selected = True
                    self.scroll_to_widget(self.selected_item)

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
                    self.scroll_to_widget(self.selected_item)

    def action_move_top(self) -> None:
        self.move_to(lambda x: x[0])

    def action_move_bottom(self) -> None:
        self.move_to(lambda x: x[-1])

    def move_to(self, selector) -> None:
        items = self.children

        if items:
            if self.selected_item:
                self.selected_item.selected = False

            self.selected_item = selector(items)
            self.selected_item.selected = True
            self.scroll_to_widget(self.selected_item)

    def action_view_info(self):
        if self.selected_item:
            self.post_message(self.TorrentViewed(self.selected_item.torrent))

    def action_toggle_torrent(self) -> None:
        if self.selected_item:
            status = self.selected_item.t_status

            if status == 'stopped':
                self.client().start_torrent(self.selected_item.t_id)
                self.post_message(MainApp.Notification("Torrent started"))
            else:
                self.client().stop_torrent(self.selected_item.t_id)
                self.post_message(MainApp.Notification("Torrent stopped"))

    def action_remove_torrent(self) -> None:
        self.remove_torrent(delete_data=False,
                            message="Remove torrent?",
                            description=("Once removed, continuing the "
                                         "transfer will require the torrent file. "
                                         "Are you sure you want to remove it?"),
                            notification="Torrent removed")

    def action_trash_torrent(self) -> None:
        self.remove_torrent(delete_data=True,
                            message="Remove torrent and delete data?",
                            description=("All data downloaded for this torrent "
                                         "will be deleted. Are you sure you "
                                         "want to remove it?"),
                            notification="Torrent and its data removed")

    def remove_torrent(self,
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

                    self.selected_item.remove()
                    self.selected_item = None

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

                    self.post_message(MainApp.Notification(notification))

            self.post_message(MainApp.Confirm(message=message,
                                              description=description,
                                              check_quit=check_quit))

    def action_verify_torrent(self) -> None:
        if self.selected_item:
            self.client().verify_torrent(self.selected_item.t_id)
            self.post_message(MainApp.Notification("Torrent send to verification"))

    def action_reannounce_torrent(self) -> None:
        if self.selected_item:
            self.client().reannounce_torrent(self.selected_item.t_id)
            self.post_message(MainApp.Notification("Torrent reannounce started"))

    def action_toggle_view_mode(self) -> None:
        if self.view_mode == 'card':
            self.view_mode = 'compact'
        elif self.view_mode == 'compact':
            self.view_mode = 'card'

        self.create_pane(self.r_tdata.torrents)

    def client(self):
        # TODO: get client
        return self.parent.parent.parent.parent.client


class TorrentItem(Static):

    selected = reactive(False)
    torrent = reactive(None)

    t_id = reactive(None)
    t_name = reactive(None)
    t_status = reactive(None)

    w_next = None
    w_prev = None

    def __init__(self, torrent):
        super().__init__()
        self.update_torrent(torrent)

    def watch_t_status(self, new_t_status):
        # For all other statuses using default colors:
        # - yellow - in progress
        # - green - complete
        self.remove_class("torrent-bar-stop", "torrent-bar-check")

        match new_t_status:
            case "stopped":
                self.add_class("torrent-bar-stop")
            case "check pending" | "checking":
                self.add_class("torrent-bar-check")

    def watch_selected(self, new_selected):
        if new_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def update_torrent(self, torrent) -> None:
        pass


class TorrentItemCompact(TorrentItem):

    t_size_total = reactive(None)
    t_size_left = reactive(None)

    t_upload_speed = reactive(0)
    t_download_speed = reactive(0)

    t_progress = reactive(0)

    def update_torrent(self, torrent) -> None:
        super().update_torrent(torrent)

        self.torrent = torrent

        self.t_id = torrent.id
        self.t_name = torrent.name
        self.t_status = torrent.status
        self.t_size_total = torrent.total_size
        self.t_size_left = torrent.left_until_done

        self.t_upload_speed = torrent.rate_upload
        self.t_download_speed = torrent.rate_download

        self.t_progress = torrent.percent_done

        self.t_eta = torrent.eta
        self.t_peers_connected = torrent.peers_connected
        self.t_leechers = torrent.peers_getting_from_us
        self.t_seeders = torrent.peers_sending_to_us
        self.t_ratio = torrent.ratio
        self.t_priority = torrent.priority

    def compose(self) -> ComposeResult:
        with Grid(id="head"):
            yield Label(self.t_name, id="name")
            yield Static("")
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCompact.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCompact.t_download_speed)

        yield (ProgressBar(total=1.0, show_percentage=False, show_eta=False)
               .data_bind(progress=TorrentItemCompact.t_progress))


class TorrentItemCard(TorrentItem):

    t_size_total = reactive(None)
    t_size_left = reactive(None)

    t_upload_speed = reactive(0)
    t_download_speed = reactive(0)

    t_progress = reactive(0)

    t_stats = reactive("")

    def update_torrent(self, torrent) -> None:
        super().update_torrent(torrent)

        self.torrent = torrent

        self.t_id = torrent.id
        self.t_name = torrent.name
        self.t_status = torrent.status
        self.t_size_total = torrent.total_size
        self.t_size_left = torrent.left_until_done

        self.t_upload_speed = torrent.rate_upload
        self.t_download_speed = torrent.rate_download

        self.t_progress = torrent.percent_done

        self.t_eta = torrent.eta
        self.t_peers_connected = torrent.peers_connected
        self.t_leechers = torrent.peers_getting_from_us
        self.t_seeders = torrent.peers_sending_to_us
        self.t_ratio = torrent.ratio
        self.t_priority = torrent.priority

        self.t_stats = self.print_stats()

    def print_stats(self) -> str:
        result = None

        size_total = Util.print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = Util.print_size(self.t_size_total - self.t_size_left)
            result = f"{size_current} / {size_total} ({self.t_progress:.2f}%)"
        else:
            result = f"{size_total} (Ratio: {self.t_ratio:.2f})"

        result = result + (f" | Status: {str(self.t_status)} | "
                           f"Seeders: {str(self.t_seeders)} | "
                           f"Leechers: {str(self.t_leechers)}")

        return result

    def compose(self) -> ComposeResult:
        with Grid(id="head"):
            yield Label(self.t_name, id="name")
            yield Static("")
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCard.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCard.t_download_speed)

        yield (ProgressBar(total=1.0, show_percentage=False, show_eta=False)
               .data_bind(progress=TorrentItemCard.t_progress))

        yield ReactiveLabel(self.t_stats, id="stats").data_bind(name=TorrentItemCard.t_stats)


class TorrentInfoPanel(ScrollableContainer):

    class TorrentViewClosed(Message):
        pass

    BINDINGS = [
            Binding("enter", "view_list", "View torrent list"),
            Binding("h", "go_left", "Go left"),
            Binding("l", "go_right", "Go right"),

            Binding("k,up", "scroll_up", "Scroll up"),
            Binding("j,down", "scroll_down", "Scroll down"),

            Binding("g", "scroll_top", "Scroll to the top"),
            Binding("G", "scroll_bottom", "Scroll to the bottom"),
            ]

    r_torrent = reactive(None)

    t_name = reactive(None)
    t_hash = reactive(None)
    t_id = reactive(None)
    t_size = reactive(None)
    t_files = reactive(None)
    t_private = reactive(None)
    t_comment = reactive(None)
    t_creator = reactive(None)

    t_status = reactive(None)
    t_location = reactive(None)

    t_date_added = reactive(None)
    t_date_started = reactive(None)
    t_date_completed = reactive(None)
    t_date_active = reactive(None)

    t_peers_active = reactive(None)
    t_peers_up = reactive(None)
    t_peers_down = reactive(None)

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Overview", id="tab-overview"):
                with ScrollableContainer(id="overview"):
                    yield Static("Details", classes="title")
                    yield Static(" ", classes="title")

                    yield Static("Name:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_name)
                    yield Static("ID:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_id)
                    yield Static("Hash:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_hash)

                    yield Static("Size:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_size)
                    yield Static("Files:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_files)
                    yield Static("Private:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_private)

                    yield Static("Comment:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_comment)
                    yield Static("Creator:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_creator)

                    yield Static(" ", classes="title")
                    yield Static("State", classes="title")
                    yield Static(" ", classes="title")

                    yield Static("Status:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_status)
                    yield Static("Location:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_location)

                    yield Static(" ", classes="title")
                    yield Static("Dates", classes="title")
                    yield Static(" ", classes="title")

                    yield Static("Added:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_added)
                    yield Static("Started:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_started)
                    yield Static("Completed:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_completed)
                    yield Static("Last active:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_active)

                    yield Static(" ", classes="title")
                    yield Static("Peers", classes="title")
                    yield Static(" ", classes="title")

                    yield Static("Active:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_peers_active)
                    yield Static("Seeding:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_peers_up)
                    yield Static("Downloading:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_peers_down)

            with TabPane("Files", id='tab-files'):
                with Container():
                    yield DataTable(id='files',
                                    cursor_type="none",
                                    zebra_stripes=True)

            with TabPane("Peers", id='tab-peers'):
                with Container():
                    yield DataTable(id='peers',
                                    cursor_type="none",
                                    zebra_stripes=True)

            with TabPane("Trackers", id='tab-trackers'):
                with Container():
                    yield DataTable(id='trackers',
                                    cursor_type="none",
                                    zebra_stripes=True)

    def on_mount(self):
        table = self.query_one("#files")
        table.add_columns("ID", "Size", "Done", "Selected", "Priority", "Name")

        table = self.query_one("#peers")
        table.add_columns("Encrypted", "Up", "Down", "Progress", "Status", "Address", "Client")

        table = self.query_one("#trackers")
        table.add_columns("Host", "Tier", "Seeders", "Leechers", "Downloads")

    def watch_r_torrent(self, new_r_torrent):
        if new_r_torrent:
            torrent = new_r_torrent

            self.t_id = str(torrent.id)
            self.t_hash = torrent.hash_string
            self.t_name = torrent.name
            self.t_size = Util.print_size(torrent.total_size)
            self.t_files = str(len(torrent.get_files()))
            self.t_private = "Yes" if torrent.is_private else "No"
            self.t_comment = torrent.comment
            self.t_creator = torrent.creator

            self.t_status = torrent.status.title()
            self.t_location = torrent.download_dir

            self.t_date_added = self.print_datetime(torrent.added_date)
            self.t_date_started = self.print_datetime(torrent.start_date)
            self.t_date_completed = self.print_datetime(torrent.done_date)
            self.t_date_active = self.print_datetime(torrent.activity_date)

            self.t_peers_active = str(torrent.peers_connected)
            self.t_peers_up = str(torrent.peers_sending_to_us)
            self.t_peers_down = str(torrent.peers_getting_from_us)

            table = self.query_one("#files")
            table.clear()

            for f in self.r_torrent.get_files():
                completion = (f.completed / f.size) * 100
                table.add_row(f.id,
                              Util.print_size(f.size),
                              f'{completion:.0f}%',
                              f.selected,
                              self.print_priority(f.priority),
                              f.name)

            table = self.query_one("#peers")
            table.clear()

            for p in self.r_torrent.peers:
                progress = p["progress"] * 100
                table.add_row("Yes" if p["isEncrypted"] else "No",
                              Util.print_speed(p["rateToClient"], True),
                              Util.print_speed(p["rateToPeer"], True),
                              f'{progress:.0f}%',
                              p["flagStr"],
                              p["address"],
                              p["clientName"])

            table = self.query_one("#trackers")
            table.clear()

            for t in self.r_torrent.tracker_stats:
                table.add_row(t.host,
                              t.tier,
                              self.print_count(t.seeder_count),
                              self.print_count(t.leecher_count),
                              self.print_count(t.download_count))

    def print_count(self, value: int) -> str:
        if value == -1:
            return "N/A"

        return value

    def print_datetime(self, value: datetime) -> str:
        if value:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return "Never"

    def print_priority(self, priority) -> str:
        if priority == -1:
            return 'Low'
        elif priority == 1:
            return 'High'
        else:
            return 'Normal'

    def action_view_list(self):
        self.post_message(self.TorrentViewClosed())

    def action_go_left(self):
        tabs = self.query_one(TabbedContent)
        active = tabs.active

        if active == 'tab-overview':
            self.post_message(self.TorrentViewClosed())
        elif active == 'tab-files':
            tabs.active = 'tab-overview'
        elif active == 'tab-peers':
            tabs.active = 'tab-files'
        elif active == 'tab-trackers':
            tabs.active = 'tab-peers'

    def action_go_right(self):
        tabs = self.query_one(TabbedContent)
        active = tabs.active

        if active == 'tab-overview':
            tabs.active = 'tab-files'
        elif active == 'tab-files':
            tabs.active = 'tab-peers'
        elif active == 'tab-peers':
            tabs.active = 'tab-trackers'

    def action_scroll_up(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").scroll_up()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").scroll_up()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()

    def action_scroll_down(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").scroll_down()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").scroll_down()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()

    def action_scroll_top(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").action_scroll_top()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").action_scroll_top()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()

    def action_scroll_bottom(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").action_scroll_bottom()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").action_scroll_bottom()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()


class MainApp(App):

    class Notification(Message):
        def __init__(self, message: str):
            super().__init__()
            self.message = message

    class Confirm(Message):
        def __init__(self, message, description, check_quit):
            super().__init__()
            self.message = message
            self.description = description
            self.check_quit = check_quit

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("t", "toggle_alt_speed", "Toggle alt speed"),
            Binding("s", "show_statistics", "Show statistics"),

            Binding("d", "toggle_dark", "Toggle dark mode", priority=True),
            Binding("?", "help", "Snow help"),
            Binding("q", "quit", "Quit", priority=True),
            ]

    r_tdata = reactive(None)

    def __init__(self, host: str, port: str,
                 username: str, password: str,
                 view_mode: str,
                 version: str):

        super().__init__()

        self.title = 'Tewi'

        self.view_mode = view_mode

        self.tewi_version = version

        self.c_host = host
        self.c_port = port

        self.client = Client(host=self.c_host, port=self.c_port,
                             username=username, password=password)

        self.transmission_version = self.client.get_session().version

    def compose(self) -> ComposeResult:
        yield InfoPanel(self.tewi_version, self.transmission_version,
                        self.c_host, self.c_port)

        with Horizontal():
            with ContentSwitcher(initial="torrent-list"):
                yield TorrentListPanel(id="torrent-list",
                                       view_mode=self.view_mode).data_bind(
                                               r_tdata=MainApp.r_tdata)
                yield TorrentInfoPanel(id="torrent-info")

        yield StatePanel().data_bind(r_tdata=MainApp.r_tdata)

    def on_mount(self) -> None:
        self.load_tdata()
        self.set_interval(5, self.load_tdata)

    def load_tdata(self) -> None:
        tdata = TransmissionData(
                session=self.client.get_session(),
                session_stats=self.client.session_stats(),
                torrents=self.client.get_torrents()
        )

        tdata.torrents.sort(key=lambda t: t.name.lower())

        self.r_tdata = tdata

    def action_toggle_alt_speed(self) -> None:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled=not alt_speed_enabled)

        if alt_speed_enabled:
            self.post_message(MainApp.Notification("Turtle Mode disabled"))
        else:
            self.post_message(MainApp.Notification("Turtle Mode enabled"))

    def action_show_statistics(self) -> None:
        self.push_screen(StatisticsDialog(self.r_tdata.session_stats))

    def action_help(self) -> None:
        self.push_screen(HelpDialog(self.screen.active_bindings.values()))

    @on(TorrentListPanel.TorrentViewed)
    def handle_torrent_view(self, event: TorrentListPanel.TorrentViewed) -> None:
        self.query_one(ContentSwitcher).current = "torrent-info"
        self.query_one(TorrentInfoPanel).r_torrent = event.torrent

    @on(TorrentInfoPanel.TorrentViewClosed)
    def handle_torrent_list(self, event: TorrentInfoPanel.TorrentViewClosed) -> None:
        self.query_one(ContentSwitcher).current = "torrent-list"

    @on(Notification)
    def handle_notification(self, event: Notification) -> None:
        self.notify(message=event.message, timeout=3)

    @on(Confirm)
    def handle_confirm(self, event: Confirm) -> None:
        self.push_screen(
                    ConfirmationDialog(message=event.message,
                                       description=event.description),
                    event.check_quit)


def cli():
    tewi_version = '0.2.0'

    parser = argparse.ArgumentParser(
            prog='tewi',
            description='Text-based interface for the Transmission BitTorrent daemon',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--view-mode', type=str, default='card',
                        choices=['card', 'compact'],
                        help='View mode for torrents in list')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Transmission daemon host for connection')
    parser.add_argument('--port', type=str, default='9091',
                        help='Transmission daemon port for connection')
    parser.add_argument('--username', type=str,
                        help='Transmission daemon username for connection')
    parser.add_argument('--password', type=str,
                        help='Transmission daemon password for connection')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + tewi_version,
                        help='Show version and exit')

    args = parser.parse_args()

    app = MainApp(host=args.host, port=args.port,
                  username=args.username, password=args.password,
                  view_mode=args.view_mode,
                  version=tewi_version)
    app.run()


if __name__ == "__main__":
    cli()
