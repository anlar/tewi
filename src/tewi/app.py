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

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, ScrollableContainer, Horizontal
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static, Label, ProgressBar, DataTable, ContentSwitcher, TabbedContent, TabPane
from textual.message import Message
from textual import on


class TransmissionData:
    def __init__(self, session, session_stats, torrents):
        self.session = session
        self.session_stats = session_stats
        self.torrents = torrents


class ReactiveLabel(Label):

    name = reactive(None)

    def render(self):
        return self.name


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
            yield Static("↑", classes="column")
            yield SpeedIndicator(classes="column").data_bind(
                    speed=StatePanel.r_upload_speed)
            yield Static("↓", classes="column")
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

            self.r_stats = f"Torrents: {len(torrents)} (Downloading: {torrents_down}, Seeding: {torrents_seed}, Paused: {torrents_stop})"

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


class SpeedIndicator(Static):

    speed = reactive(0)

    def render(self) -> str:
        return self.print_speed(self.speed)

    def print_speed(self, num: int,
                    suffix: str="B", speed_bytes: int=1000) -> str:

        r_unit = None
        r_num = None

        for i in (("", 0), ("K", 0), ("M", 2), ("G", 2), ("T", 2), ("P", 2), ("E", 2), ("Z", 2), ("Y", 2)):

            if abs(num) < speed_bytes:
                r_unit = i[0]
                r_num = round(num, i[1])
                break
            num /= speed_bytes

        r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

        return f"{r_size} {r_unit}{suffix}"


class TorrentListPanel(ScrollableContainer):

    BINDINGS = [
            Binding("k,up", "move_up", "Move up"),
            Binding("j,down", "move_down", "Move down"),

            Binding("g", "move_top", "Go to the first item"),
            Binding("G", "move_bottom", "Go to the last item"),

            Binding("enter,l", "view_info", "View torrent info"),
            ]

    r_tdata = reactive(None)

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
        self.remove_children()

        self.selected_item = None

        w_prev = None
        for t in torrents:
            item = TorrentItem(t)
            self.mount(item)

            if w_prev:
                w_prev.w_next = item
                item.w_prev = w_prev
                w_prev = item
            else:
                w_prev = item

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

    class TorrentViewed(Message):
        def __init__(self, torrent) -> None:
            super().__init__()
            self.torrent = torrent

    def action_view_info(self):
        if self.selected_item:
            self.post_message(self.TorrentViewed(self.selected_item.torrent))

class TorrentItem(Static):
    # TODO: refactor
    selected = reactive(False)

    torrent = reactive(None)

    t_id = reactive(None)
    t_name = reactive(None)
    t_status = reactive(None)
    t_size_total = reactive(None)
    t_size_left = reactive(None)

    t_upload_speed = reactive(0)
    t_download_speed = reactive(0)

    t_progress = reactive(0)

    t_stats = reactive("")

    w_next = None
    w_prev = None

    def __init__(self, torrent):
        super().__init__()
        self.update_torrent(torrent)

    def watch_selected(self, new_selected):
        if new_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

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

    def update_torrent(self, torrent) -> None:
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

        result = result + f" | Status: {str(self.t_status)} | Seeders: {str(self.t_seeders)} | Leechers: {str(self.t_leechers)}"

        return result

    def compose(self) -> ComposeResult:
        with Grid(id="head"):
            yield Label(self.t_name, id="name")
            yield Static("")
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItem.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItem.t_download_speed)

        yield (ProgressBar(total=1.0, show_percentage=False, show_eta=False)
               .data_bind(progress=TorrentItem.t_progress))

        yield ReactiveLabel(self.t_stats, id="stats").data_bind(name=TorrentItem.t_stats)


class TorrentInfoPanel(ScrollableContainer):

    BINDINGS = [
            Binding("h,enter", "view_list", "View torrent list"),
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
            with TabPane("Overview"):
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

    def print_datetime(self, value: datetime) -> str:
        if value:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return "Never"

    def action_view_list(self):
        self.post_message(self.TorrentViewClosed())

    class TorrentViewClosed(Message):
        pass


class MainApp(App):

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("q", "quit", "Quit"),
            ]

    r_tdata = reactive(None)

    def __init__(self, host: str, port: str,
                 username: str, password: str,
                 version: str):

        super().__init__()

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
                yield TorrentListPanel(id="torrent-list").data_bind(
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

    @on(TorrentListPanel.TorrentViewed)
    def handle_torrent_view(self, event: TorrentListPanel.TorrentViewed) -> None:
        self.query_one(ContentSwitcher).current = "torrent-info"
        self.query_one(TorrentInfoPanel).r_torrent = event.torrent

    @on(TorrentInfoPanel.TorrentViewClosed)
    def handle_torrent_list(self, event: TorrentInfoPanel.TorrentViewClosed) -> None:
        self.query_one(ContentSwitcher).current = "torrent-list"


class Util:
    def print_size(num: int, suffix="B", size_bytes=1000):
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


def cli():
    tewi_version = '0.1.0'

    parser = argparse.ArgumentParser(
            prog='tewi',
            description='Text-based interface for the Transmission BitTorrent daemon',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

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
                  version=tewi_version)
    app.run()


if __name__ == "__main__":
    cli()
