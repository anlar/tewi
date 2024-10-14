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


class TransmissionSession:
    def __init__(self, session, session_stats, torrents):
        self.session = session
        self.session_stats = session_stats
        self.torrents = torrents


class TorrentInfoWidget(Widget):
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
                with ScrollableContainer(id="info-overview"):
                    yield Static("Details", classes="info-overview-title")
                    yield Static(" ", classes="info-overview-title")

                    yield Static("Name:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_name)
                    yield Static("ID:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_id)
                    yield Static("Hash:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_hash)

                    yield Static("Size:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_size)
                    yield Static("Files:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_files)
                    yield Static("Private:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_private)

                    yield Static("Comment:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_comment)
                    yield Static("Creator:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_creator)

                    yield Static(" ", classes="info-overview-title")
                    yield Static("State", classes="info-overview-title")
                    yield Static(" ", classes="info-overview-title")

                    yield Static("Status:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_status)
                    yield Static("Location:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_location)

                    yield Static(" ", classes="info-overview-title")
                    yield Static("Dates", classes="info-overview-title")
                    yield Static(" ", classes="info-overview-title")

                    yield Static("Added:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_date_added)
                    yield Static("Started:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_date_started)
                    yield Static("Completed:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_date_completed)
                    yield Static("Last active:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_date_active)

                    yield Static(" ", classes="info-overview-title")
                    yield Static("Limits", classes="info-overview-title")
                    yield Static(" ", classes="info-overview-title")

                    yield Static(" ", classes="info-overview-title")
                    yield Static("Peers", classes="info-overview-title")
                    yield Static(" ", classes="info-overview-title")

                    yield Static("Active:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_peers_active)
                    yield Static("Seeding:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_peers_up)
                    yield Static("Downloading:", classes="info-overview-name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoWidget.t_peers_down)

    def update_torrent(self, torrent):
        self.t_id = str(torrent.id)
        self.t_hash = torrent.hash_string
        self.t_name = torrent.name
        self.t_size = print_size(torrent.total_size)
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
            return ""


class StatisticsDialog(ModalScreen[bool]):
    BINDINGS = [
            Binding("q,escape", "close", "Cancel", priority=True),
            ]

    def __init__(self, session_stats) -> None:
        self.session_stats = session_stats
        super().__init__()

    def compose(self) -> ComposeResult:
        yield StatisticsWidget(self.session_stats)

    def action_close(self) -> None:
        self.dismiss(False)


class StatisticsWidget(Widget):

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
        yield Static("Current Session", classes="statistics-title")
        yield Static("  Uploaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_upload)
        yield Static("  Downloaded:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_download)
        yield Static("  Ratio:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_ratio)
        yield Static("  Running Time:")
        yield ReactiveLabel().data_bind(name=StatisticsWidget.r_time)
        yield Static(" ", classes="statistics-title")
        yield Static("Total", classes="statistics-title")
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
        self.border_subtitle = 'Q(uit)'

        # current stats

        self.r_upload = print_size(self.session_stats.current_stats.uploaded_bytes)
        self.r_download = print_size(self.session_stats.current_stats.downloaded_bytes)

        self.r_ratio = self.print_ratio(self.session_stats.current_stats.uploaded_bytes,
                                        self.session_stats.current_stats.downloaded_bytes)

        self.r_time = self.print_time(self.session_stats.current_stats.seconds_active)

        # cumulative stats

        self.r_total_upload = print_size(self.session_stats.cumulative_stats.uploaded_bytes)
        self.r_total_download = print_size(self.session_stats.cumulative_stats.downloaded_bytes)

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


class HelpDialog(ModalScreen[bool]):
    BINDINGS = [
            Binding("q,escape", "close", "Cancel", priority=True),
            ]

    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__()

    def compose(self) -> ComposeResult:
        yield HelpWidget(self.bindings)

    def action_close(self) -> None:
        self.dismiss(False)


class HelpWidget(Widget):

    def __init__(self, bindings) -> None:
        self.bindings = bindings
        super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield DataTable()

    def on_mount(self) -> None:
        self.border_title = 'Help'
        self.border_subtitle = 'Q(uit)'

        table = self.query_one(DataTable)
        table.add_columns("Key", "Command")

        for b in self.bindings:
            table.add_row(b.key, b.description)

        table.cursor_type = "none"
        table.zebra_stripes = True


class ConfirmationDialog(ModalScreen[bool]):
    BINDINGS = [
            Binding("y", "confirm", "Yes", priority=True),
            Binding("n,escape", "close", "Cancel", priority=True),
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
        self.border_subtitle = 'Y(es) / N(o)'


class ReactiveLabel(Label):
    name = reactive("")

    def render(self):
        return self.name


class TorrentItem(Static):
    """Torrent item in main list"""

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

        size_total = print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = print_size(self.t_size_total - self.t_size_left)
            result = f"{size_current} / {size_total} ({self.t_progress:.2f}%)"
        else:
            result = f"{size_total} (Ratio: {self.t_ratio:.2f})"

        result = result + f" | Status: {str(self.t_status)} | Seeders: {str(self.t_seeders)} | Leechers: {str(self.t_leechers)}"

        return result

    def compose(self) -> ComposeResult:
        with Grid(id="torrent-item-head"):
            yield Label(self.t_name, id="torrent-item-head-name")
            yield Static("")
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItem.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItem.t_download_speed)

        yield (ProgressBar(total=1.0, show_percentage=False, show_eta=False)
               .data_bind(progress=TorrentItem.t_progress))

        yield ReactiveLabel(self.t_stats, id="torrent-item-stats").data_bind(name=TorrentItem.t_stats)


class StatusLine(Widget):

    r_session = reactive(None)

    # recompose whole line to update blocks width
    r_stats = reactive('', recompose=True)
    r_alt_speed = reactive('', recompose=True)
    r_alt_delimiter = reactive('', recompose=True)

    r_upload_speed = reactive('')
    r_download_speed = reactive('')

    def compose(self) -> ComposeResult:
        yield ReactiveLabel(self.r_stats, classes="bottom-pane-column").data_bind(name=StatusLine.r_stats)
        yield Static("", classes="bottom-pane-column")
        yield ReactiveLabel(self.r_alt_speed, classes="bottom-pane-column bottom-pane-alt").data_bind(name=StatusLine.r_alt_speed)
        yield ReactiveLabel('', classes="bottom-pane-column bottom-pane-column-delimiter").data_bind(name=StatusLine.r_alt_delimiter)
        yield Static("↑", classes="bottom-pane-column bottom-pane-arrow")
        yield SpeedIndicator(classes="bottom-pane-column").data_bind(speed=StatusLine.r_upload_speed)
        yield Static("↓", classes="bottom-pane-column bottom-pane-arrow")
        yield SpeedIndicator(classes="bottom-pane-column").data_bind(speed=StatusLine.r_download_speed)

    def watch_r_session(self, new_r_session):
        if new_r_session:
            session = new_r_session.session
            session_stats = new_r_session.session_stats
            torrents = new_r_session.torrents

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


class SpeedIndicator(Widget):

    speed = reactive(0)

    def render(self) -> str:
        return self.print_speed(self.speed)

    def print_speed(self, num, suffix="B", speed_bytes=1000) -> str:
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


class MainApp(App):
    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("k,up", "scroll_up", "Move up"),
            Binding("j,down", "scroll_down", "Move down"),

            Binding("g", "jump_up", "Go to the first item"),
            Binding("G", "jump_down", "Go to the last item"),

            Binding("l", "view_torrent", "View torrent info"),
            Binding("h", "view_torrents", "View torrents list"),
            Binding("enter", "toggle_views", "Switch torrent list/info"),

            Binding("p", "toggle_torrent", "Toggle torrent"),
            Binding("r", "remove_torrent", "Remove torrent"),
            Binding("R", "trash_torrent", "Trash torrent"),
            Binding("v", "verify_torrent", "Verify torrent"),
            Binding("n", "reannounce_torrent", "Reannounce torrent"),

            Binding("t", "toggle_alt_speed", "Toggle alt speed"),

            Binding("s", "show_statistics", "Show statistics"),


            Binding("?", "help", "Help"),
            Binding("q", "quit", "Quit"),
            ]

    r_session = reactive(None)

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

        self.selected_item = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-pane"):
            yield Static(f'Tewi {self.tewi_version}', classes='top-pane-column')
            yield Static('»»»', classes='top-pane-column top-pane-column-delimiter')
            yield Static(f'Transmission {self.transmission_version}', classes='top-pane-column')
            yield Static('»»»', classes='top-pane-column top-pane-column-delimiter')
            yield Static(f'{self.c_host}:{self.c_port}', classes='top-pane-column')
            yield Static('', classes='top-pane-column top-pane-column-space')
            yield Static('?: Help', classes='top-pane-column')
            yield Static('', classes='top-pane-column')
            yield Static('Q: Quit', classes='top-pane-column')

        with Horizontal():
            with ContentSwitcher(initial="torrents"):
                yield ScrollableContainer(id="torrents")
                yield TorrentInfoWidget(id="torrent-info")

        yield StatusLine().data_bind(r_session=MainApp.r_session)

    def on_mount(self) -> None:
        self.load_session()
        self.set_interval(5, self.load_session)

    def action_toggle_torrent(self) -> None:
        if self.selected_item:
            status = self.selected_item.t_status

            if status == 'stopped':
                self.client.start_torrent(self.selected_item.t_id)
                self.tewi_notify("Torrent started")
            else:
                self.client.stop_torrent(self.selected_item.t_id)
                self.tewi_notify("Torrent stopped")

    def action_verify_torrent(self) -> None:
        if self.selected_item:
            self.client.verify_torrent(self.selected_item.t_id)
            self.tewi_notify("Torrent send to verification")

    def action_reannounce_torrent(self) -> None:
        if self.selected_item:
            self.client.reannounce_torrent(self.selected_item.t_id)
            self.tewi_notify("Torrent reannounce started")

    def action_remove_torrent(self) -> None:
        self.remove_torrent(delete_data=False,
                            message="Remove torrent?",
                            description="Once removed, continuing the transfer will require the torrent file. Are you sure you want to remove it?",
                            notification="Torrent removed")

    def action_trash_torrent(self) -> None:
        self.remove_torrent(delete_data=True,
                            message="Remove torrent and delete data?",
                            description="All data downloaded for this torrent will be deleted. Are you sure you want to remove it?",
                            notification="Torrent and its data removed")

    def remove_torrent(self,
                       delete_data: bool,
                       message: str,
                       description: str,
                       notification: str) -> None:

        if self.selected_item:

            def check_quit(confirmed: bool | None) -> None:
                if confirmed:
                    self.client.remove_torrent(self.selected_item.t_id,
                                               delete_data=delete_data)

                    self.tewi_notify(notification)

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
                        self.query_one("#torrents").scroll_to_widget(self.selected_item)

            self.push_screen(
                        ConfirmationDialog(message=message,
                                           description=description),
                        check_quit)

    def action_show_statistics(self) -> None:
        self.push_screen(StatisticsDialog(self.r_session.session_stats))

    def action_help(self) -> None:
        self.push_screen(HelpDialog(bindings=self.BINDINGS))

    def action_scroll_up(self) -> None:
        items = self.query(TorrentItem)

        if items:
            if self.selected_item is None:
                item = items[-1]
                item.selected = True
                self.selected_item = item
                self.query_one("#torrents").scroll_to_widget(self.selected_item)
            else:
                if self.selected_item.w_prev:
                    self.selected_item.selected = False
                    self.selected_item = self.selected_item.w_prev
                    self.selected_item.selected = True
                    self.query_one("#torrents").scroll_to_widget(self.selected_item)

    def action_scroll_down(self) -> None:
        items = self.query(TorrentItem)

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
                    self.query_one("#torrents").scroll_to_widget(self.selected_item)

    def action_jump_up(self) -> None:
        self.jump_to(lambda x: x[0])

    def action_jump_down(self) -> None:
        self.jump_to(lambda x: x[-1])

    def jump_to(self, selector) -> None:
        items = self.query(TorrentItem)

        if items:
            if self.selected_item:
                self.selected_item.selected = False

            self.selected_item = selector(items)
            self.selected_item.selected = True
            self.query_one("#torrents").scroll_to_widget(self.selected_item)

    def action_view_torrent(self):
        if self.selected_item:
            switcher = self.query_one(ContentSwitcher)
            switcher.current = 'torrent-info'
            self.query_one(TorrentInfoWidget).update_torrent(self.selected_item.torrent)

    def action_view_torrents(self):
        switcher = self.query_one(ContentSwitcher)
        switcher.current = 'torrents'

    def action_toggle_views(self):
        if self.selected_item:
            switcher = self.query_one(ContentSwitcher)

            if switcher.current == 'torrents':
                switcher.current = 'torrent-info'
                self.query_one(TorrentInfoWidget).update_torrent(self.selected_item.torrent)
            else:
                switcher.current = 'torrents'

    def action_toggle_alt_speed(self) -> None:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled=not alt_speed_enabled)

        if alt_speed_enabled:
            self.tewi_notify("Turtle Mode disabled")
        else:
            self.tewi_notify("Turtle Mode enabled")

    def watch_r_session(self, new_r_session):
        if new_r_session:
            session = new_r_session

            # TODO: better handle for cases when updates came when
            # main screen is on the background
            try:
                if self.is_equal_to_pane(session.torrents):
                    items = self.query_one("#torrents").children

                    for i, torrent in enumerate(session.torrents):
                        items[i].update_torrent(torrent)
                else:
                    self.create_pane(session)
            except NoMatches:
                pass

    def create_pane(self, session) -> None:
        torrents_pane = self.query_one("#torrents")
        torrents_pane.remove_children()

        self.selected_item = None

        w_prev = None
        for t in session.torrents:
            item = TorrentItem(t)
            torrents_pane.mount(item)

            if w_prev:
                w_prev.w_next = item
                item.w_prev = w_prev
                w_prev = item
            else:
                w_prev = item

        self.query_one("#torrents").scroll_home()

    def is_equal_to_pane(self, torrents) -> bool:
        items = self.query_one("#torrents").children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i].t_id:
                return False

        return True

    def load_session(self) -> None:
        session = TransmissionSession(
                session=self.client.get_session(),
                session_stats=self.client.session_stats(),
                torrents=self.client.get_torrents()
        )

        session.torrents.sort(key=lambda t: t.name.lower())

        self.log(f'Load session from Transmission: {vars(session.session)}')
        self.log(f'Load session_stats from Transmission: {vars(session.session_stats)}')
        self.log(f'Load {len(session.torrents)} torrents from Transmission')

        self.r_session = session

    def tewi_notify(self, message: str) -> None:
        self.notify(message=message, timeout=3)


def print_size(num, suffix="B", size_bytes=1000):
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
    parser.add_argument('--version', action='version', version='%(prog)s ' + tewi_version,
                        help='Show version and exit')

    args = parser.parse_args()

    app = MainApp(host=args.host, port=args.port,
                  username=args.username, password=args.password,
                  version=tewi_version)
    app.run()


if __name__ == "__main__":
    cli()
