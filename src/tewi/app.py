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

__version__ = '0.6.0'

from datetime import datetime
from functools import cache, wraps
from typing import NamedTuple
import argparse
import logging
import math
import os
import pathlib
import textwrap
import time

from transmission_rpc import Client
from transmission_rpc.error import TransmissionError
from transmission_rpc.session import Session, SessionStats

from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, ScrollableContainer, Horizontal, Container
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static, Label, ProgressBar, DataTable, ContentSwitcher, TabbedContent, TabPane, TextArea

from geoip2fast import GeoIP2Fast

import pyperclip


# Logging

logger = logging.getLogger('tewi')


def log_time(func):

    @wraps(func)
    def log_time_wrapper(*args, **kwargs):
        start_time = time.perf_counter()

        result = func(*args, **kwargs)

        end_time = time.perf_counter()

        total_time_ms = (end_time - start_time) * 1000

        if total_time_ms > 1:
            logger.info(f'Function "{func.__qualname__}": {total_time_ms:.4f} ms')

        return result

    return log_time_wrapper


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


# Common utils

class Util:

    geoip = GeoIP2Fast()

    @cache
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

    @cache
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

    @cache
    def print_time(seconds, units: int = 1) -> str:
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
                result.append(f"{value:.0f} {name}")
        return ', '.join(result[:units])

    @cache
    def get_country(address: str) -> str:
        return Util.geoip.lookup(address).country_name


# Common UI components

class ReactiveLabel(Label):

    name = reactive(None)

    def render(self):
        if self.name:
            return self.name
        else:
            return ''


# Common torrent-related widgets

class SpeedIndicator(Static):

    speed = reactive(0)

    def render(self) -> str:
        return Util.print_speed(self.speed)


class PageIndicator(Static):

    state = reactive(None)

    def render(self) -> str:
        # hide indicator when single page
        if self.state is None or self.state.total == 1:
            return ''
        else:
            # include padding by spaces
            return f' [ {self.state.current + 1} / {self.state.total} ] '


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
            elif key == 'quotation_mark':
                key = '"'

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

        self.r_time = Util.print_time(self.session_stats.current_stats.seconds_active)

        # cumulative stats

        self.r_total_upload = Util.print_size(self.session_stats.cumulative_stats.uploaded_bytes)
        self.r_total_download = Util.print_size(self.session_stats.cumulative_stats.downloaded_bytes)

        self.r_total_ratio = self.print_ratio(self.session_stats.cumulative_stats.uploaded_bytes,
                                              self.session_stats.cumulative_stats.downloaded_bytes)

        self.r_total_time = Util.print_time(self.session_stats.cumulative_stats.seconds_active)
        self.r_total_started = f"{self.session_stats.cumulative_stats.session_count} times"

    def print_ratio(self, uploaded, downloaded) -> str:
        if downloaded == 0:
            return "∞"

        ratio = uploaded / downloaded

        return f"{ratio:.2f}"


class AddTorrentDialog(ModalScreen):

    def __init__(self, session):
        self.session = session
        super().__init__()

    def compose(self) -> ComposeResult:
        yield AddTorrentWidget(self.session)


class AddTorrentWidget(Static):

    r_download_dir = reactive('')

    BINDINGS = [
            Binding("enter", "add", "Add torrent", priority=True),
            Binding("escape", "close", "Close"),
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
        self.border_subtitle = '[Enter] Add / [ESC] Close'

        free_space = Util.print_size(self.session.download_dir_free_space)
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
        text = pyperclip.paste()

        if text:
            if self.is_link(text):
                return text

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

    def __init__(self, torrent):
        self.torrent = torrent
        super().__init__()

    def compose(self) -> ComposeResult:
        yield UpdateTorrentLabelsWidget(self.torrent)


class UpdateTorrentLabelsWidget(Static):

    BINDINGS = [
            Binding("enter", "update", "Update labels", priority=True),
            Binding("escape", "close", "Close"),
            ]

    def __init__(self, torrent):
        self.torrent = torrent
        super().__init__()

    def compose(self) -> ComposeResult:
        yield TextArea()

    def on_mount(self) -> None:
        self.border_title = 'Update torrent labels (comma-separated list)'
        self.border_subtitle = '[Enter] Update / [ESC] Close'

        text_area = self.query_one(TextArea)

        if len(self.torrent.labels) > 0:
            text_area.load_text(", ".join(self.torrent.labels))

        text_area.cursor_location = text_area.document.end

    def action_update(self) -> None:
        value = self.query_one(TextArea).text

        self.post_message(MainApp.TorrentLabelsUpdated(
            self.torrent, value))

        self.parent.dismiss(False)

    def action_close(self) -> None:
        self.parent.dismiss(False)


class SortOrderDialog(ModalScreen):

    def compose(self) -> ComposeResult:
        yield SortOrderWidget()


class SortOrderWidget(Static):

    BINDINGS = [
            Binding("escape,x", "close", "Close"),
            ]

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="none",
                        zebra_stripes=True)

    def on_mount(self) -> None:
        self.border_title = 'Sort order'
        self.border_subtitle = '[X] Close'

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


# Core UI panels

class InfoPanel(Static):

    @log_time
    def __init__(self,
                 w_version: str, w_trans_version: str,
                 w_host: str, w_port: str):

        self.w_version = w_version
        self.w_trans_version = w_trans_version
        self.w_host = w_host
        self.w_port = w_port

        super().__init__()

    @log_time
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

    r_tsession = reactive(None)

    # recompose whole line to update blocks width
    r_page = reactive(None, recompose=True)
    r_stats = reactive('', recompose=True)
    r_sort = reactive('', recompose=True)
    r_alt_speed = reactive('', recompose=True)
    r_alt_delimiter = reactive('', recompose=True)

    r_stats_size = reactive('', recompose=True)

    r_upload_speed = reactive(0)
    r_download_speed = reactive(0)

    @log_time
    def compose(self) -> ComposeResult:
        with Grid(id="state-panel"):
            yield PageIndicator(classes="column page").data_bind(
                    state=StatePanel.r_page)
            yield ReactiveLabel(classes="column").data_bind(
                    name=StatePanel.r_stats)
            yield ReactiveLabel(classes="column").data_bind(
                    name=StatePanel.r_stats_size)
            yield ReactiveLabel(classes="column sort").data_bind(
                    name=StatePanel.r_sort)
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

    @log_time
    def watch_r_tsession(self, new_r_tsession):
        if new_r_tsession:
            session = new_r_tsession.session
            session_stats = new_r_tsession.session_stats

            self.r_stats = self.print_stats(new_r_tsession, session_stats)

            complete_size = Util.print_size(new_r_tsession.torrents_complete_size)
            total_size = Util.print_size(new_r_tsession.torrents_total_size)

            if complete_size < total_size:
                self.r_stats_size = f'Size: {complete_size} / {total_size}'
            else:
                self.r_stats_size = f'Size: {complete_size}'

            sort_order = new_r_tsession.sort_order.name
            sort_order_asc = new_r_tsession.sort_order_asc
            sort_arrow = '' if sort_order_asc else '↑'
            self.r_sort = f'Sort: {sort_order}{sort_arrow}'

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

    def print_stats(self, session, session_stats) -> str:
        stats = f"Torrents: {session_stats.torrent_count}"

        statuses = []

        if session.torrents_down > 0:
            statuses.append(f"Downloading: {session.torrents_down}")

        if session.torrents_seed > 0:
            statuses.append(f"Seeding: {session.torrents_seed}")

        if session.torrents_check > 0:
            statuses.append(f"Verifying: {session.torrents_check}")

        if session.torrents_stop > 0:
            statuses.append(f"Paused: {session.torrents_stop}")

        if len(statuses) > 0:
            stats = f"{stats} ({', '.join(statuses)})"

        return stats


class TorrentItem(Static):

    selected = reactive(False)
    torrent = reactive(None)

    t_id = reactive(None)
    t_name = reactive(None)
    t_status = reactive(None)

    t_size_total = reactive(None)
    t_size_left = reactive(None)
    t_ratio = reactive(0)
    t_progress = reactive(0)
    t_eta = reactive(None)

    t_upload_speed = reactive(0)
    t_download_speed = reactive(0)

    t_size_stats = reactive("")

    w_next = None
    w_prev = None

    @log_time
    def __init__(self, torrent):
        super().__init__()
        self.update_torrent(torrent)

    @log_time
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

    @log_time
    def watch_selected(self, new_selected):
        if new_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    @log_time
    def update_torrent(self, torrent) -> None:
        self.torrent = torrent

        self.t_id = torrent.id
        self.t_name = torrent.name
        self.t_status = torrent.status

        self.t_size_total = torrent.total_size
        self.t_size_left = torrent.left_until_done
        self.t_progress = torrent.percent_done
        self.t_eta = torrent.eta

        self.t_upload_speed = torrent.rate_upload
        self.t_download_speed = torrent.rate_download
        self.t_ratio = torrent.ratio

        self.t_size_stats = self.print_size_stats()

    @log_time
    def print_size_stats(self) -> str:
        result = None

        size_total = Util.print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = Util.print_size(self.t_size_total - self.t_size_left)
            result = f"{size_current} / {size_total} ({(self.t_progress * 100):.1f}%)"

            if self.t_eta:
                result = f"{result} ({Util.print_time(self.t_eta.total_seconds(), 2)})"
        else:
            result = f"{size_total} (Ratio: {self.t_ratio:.2f})"

        return result


class TorrentItemOneline(TorrentItem):

    @log_time
    def compose(self) -> ComposeResult:
        yield Label(self.t_name, id="name")

        with Grid(id="speed"):
            yield ReactiveLabel(id="stats").data_bind(
                    name=TorrentItemCompact.t_size_stats)
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(
                    speed=TorrentItemOneline.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(
                    speed=TorrentItemOneline.t_download_speed)

    @log_time
    def watch_t_status(self, new_t_status):
        self.remove_class("torrent-complete",
                          "torrent-incomplete",
                          "torrent-stop",
                          "torrent-check")

        match new_t_status:
            case "stopped":
                self.add_class("torrent-stop")
            case "check pending" | "checking":
                self.add_class("torrent-check")
            case "download pending" | "downloading":
                self.add_class("torrent-incomplete")
            case "seed pending" | "seeding":
                self.add_class("torrent-complete")


class TorrentItemCompact(TorrentItem):

    @log_time
    def compose(self) -> ComposeResult:
        yield Label(self.t_name, id="name")

        with Grid(id="speed"):
            yield ReactiveLabel(id="stats").data_bind(
                    name=TorrentItemCompact.t_size_stats)
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCompact.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCompact.t_download_speed)

        yield (ProgressBar(total=1.0, show_percentage=False, show_eta=False)
               .data_bind(progress=TorrentItemCompact.t_progress))


class TorrentItemCard(TorrentItem):

    t_stats_uploaded = reactive('')
    t_stats_peer = reactive("")
    t_stats_seed = reactive("")
    t_stats_leech = reactive("")

    @log_time
    def compose(self) -> ComposeResult:
        yield Label(self.t_name, id="name")

        with Grid(id="speed"):
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCard.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItemCard.t_download_speed)

        yield (ProgressBar(total=1.0, show_percentage=False, show_eta=False)
               .data_bind(progress=TorrentItemCard.t_progress))

        with Grid(id="stats"):
            yield ReactiveLabel().data_bind(
                    name=TorrentItemCard.t_size_stats)
            yield ReactiveLabel().data_bind(
                    name=TorrentItemCard.t_stats_uploaded)
            yield ReactiveLabel().data_bind(
                    name=TorrentItemCard.t_status)
            yield ReactiveLabel().data_bind(
                    name=TorrentItemCard.t_stats_peer)

    @log_time
    def update_torrent(self, torrent) -> None:
        super().update_torrent(torrent)

        self.t_eta = torrent.eta
        self.t_peers_connected = torrent.peers_connected
        self.t_leechers = torrent.peers_getting_from_us
        self.t_seeders = torrent.peers_sending_to_us
        self.t_ratio = torrent.ratio
        self.t_priority = torrent.priority

        self.t_stats_uploaded = 'Uploaded: ' + Util.print_size(torrent.uploaded_ever)

        # implying that there won't be more than 9999 peers
        self.t_stats_peer = (f'{self.t_peers_connected: >4} peers '
                             f'{self.t_seeders: >4} seeders '
                             f'{self.t_leechers: >4} leechers')


class TorrentListPanel(ScrollableContainer):

    class TorrentViewed(Message):

        def __init__(self, torrent) -> None:
            super().__init__()
            self.torrent = torrent

    BINDINGS = [
            Binding("k,up", "move_up", "Move up"),
            Binding("j,down", "move_down", "Move down"),

            Binding("g", "move_top", "Go to the first item"),
            Binding("home", "move_top", "Go to the first item"),
            Binding("G", "move_bottom", "Go to the last item"),
            Binding("end", "move_bottom", "Go to the last item"),

            Binding("enter,l", "view_info", "View torrent info"),

            Binding("a", "add_torrent", "Add torrent"),
            Binding("L", "update_torrent_labels", "Update labels"),
            Binding("s", "sort_order", "Select sort order"),

            Binding("p", "toggle_torrent", "Toggle torrent"),
            Binding("r", "remove_torrent", "Remove torrent"),
            Binding("R", "trash_torrent", "Trash torrent"),
            Binding("v", "verify_torrent", "Verify torrent"),
            Binding("n", "reannounce_torrent", "Reannounce torrent"),

            Binding("y", "start_all_torrents", "Start all torrents"),
            Binding("Y", "stop_all_torrents", "Stop all torrents"),

            Binding("m", "toggle_view_mode", "Toggle torrents view mode"),
            ]

    r_torrents = reactive(None)

    selected_item = reactive(None)

    @log_time
    def __init__(self, id: str, view_mode: str, page_size: str):
        self.view_mode = view_mode
        self.page_size = page_size
        super().__init__(id=id)

    def torrent_idx(self, torrent) -> int:
        return next((idx) for (idx, t) in enumerate(self.r_torrents) if t.id == torrent.id)

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

            # detect current page by selected item

            if self.selected_item:
                selected_idx = self.torrent_idx(self.selected_item.torrent)
                current_page = selected_idx // self.page_size
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
    def action_view_info(self):
        if self.selected_item:
            self.post_message(self.TorrentViewed(self.selected_item.torrent))

    @log_time
    def action_add_torrent(self) -> None:
        self.post_message(MainApp.OpenAddTorrent())

    @log_time
    def action_update_torrent_labels(self) -> None:
        if self.selected_item:
            self.post_message(
                    MainApp.OpenUpdateTorrentLabels(
                        self.selected_item.torrent))

    @log_time
    def action_sort_order(self) -> None:
        self.post_message(MainApp.OpenSortOrder())

    @log_time
    def action_toggle_torrent(self) -> None:
        if self.selected_item:
            status = self.selected_item.t_status

            if status == 'stopped':
                self.client().start_torrent(self.selected_item.t_id)
                self.post_message(MainApp.Notification("Torrent started"))
            else:
                self.client().stop_torrent(self.selected_item.t_id)
                self.post_message(MainApp.Notification("Torrent stopped"))

    @log_time
    def action_remove_torrent(self) -> None:
        self.remove_torrent(delete_data=False,
                            message="Remove torrent?",
                            description=("Once removed, continuing the "
                                         "transfer will require the torrent file. "
                                         "Are you sure you want to remove it?"),
                            notification="Torrent removed")

    @log_time
    def action_trash_torrent(self) -> None:
        self.remove_torrent(delete_data=True,
                            message="Remove torrent and delete data?",
                            description=("All data downloaded for this torrent "
                                         "will be deleted. Are you sure you "
                                         "want to remove it?"),
                            notification="Torrent and its data removed")

    @log_time
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
        if self.selected_item:
            self.client().verify_torrent(self.selected_item.t_id)
            self.post_message(MainApp.Notification("Torrent send to verification"))

    @log_time
    def action_reannounce_torrent(self) -> None:
        if self.selected_item:
            self.client().reannounce_torrent(self.selected_item.t_id)
            self.post_message(MainApp.Notification("Torrent reannounce started"))

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
    def client(self):
        # TODO: get client
        return self.parent.parent.parent.parent.client


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
    t_pieces = reactive(None)
    t_privacy = reactive(None)
    t_comment = reactive(None)
    t_creator = reactive(None)
    t_labels = reactive(None)

    t_status = reactive(None)
    t_location = reactive(None)
    t_downloaded = reactive(None)
    t_uploaded = reactive(None)
    t_ratio = reactive(None)
    t_error = reactive(None)

    t_date_added = reactive(None)
    t_date_started = reactive(None)
    t_date_completed = reactive(None)
    t_date_active = reactive(None)

    t_peers_active = reactive(None)
    t_peers_up = reactive(None)
    t_peers_down = reactive(None)

    @log_time
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
                    yield Static("Pieces:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_pieces)
                    yield Static("Privacy:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_privacy)

                    yield Static("Comment:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_comment)
                    yield Static("Creator:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_creator)
                    yield Static("Labels:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_labels)

                    yield Static(" ", classes="title")
                    yield Static("State", classes="title")
                    yield Static(" ", classes="title")

                    yield Static("Status:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_status)
                    yield Static("Location:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_location)
                    yield Static("Downloaded:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_downloaded)
                    yield Static("Uploaded:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_uploaded)
                    yield Static("Ratio:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_ratio)
                    yield Static("Error:", classes="name")
                    yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_error)

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

    @log_time
    def on_mount(self):
        table = self.query_one("#files")
        table.add_columns("ID", "Size", "Progress", "Selected", "Priority", "Name")

        table = self.query_one("#peers")
        table.add_columns("Encrypted", "Up", "Down", "Progress", "Status", "Country", "Address", "Client")

        table = self.query_one("#trackers")
        table.add_columns("Host", "Tier", "Seeders", "Leechers", "Downloads")

    @log_time
    def watch_r_torrent(self, new_r_torrent):
        if new_r_torrent:
            torrent = new_r_torrent

            self.t_id = str(torrent.id)
            self.t_hash = torrent.hash_string
            self.t_name = torrent.name
            self.t_size = Util.print_size(torrent.total_size)
            self.t_files = str(len(torrent.get_files()))
            self.t_pieces = f"{torrent.piece_count} @ {Util.print_size(torrent.piece_size, size_bytes=1024)}"

            if torrent.is_private:
                self.t_privacy = "Private to this tracker -- DHT and PEX disabled"
            else:
                self.t_privacy = "Public torrent"

            self.t_comment = torrent.comment if torrent.comment else "None"
            self.t_creator = torrent.creator if torrent.creator else "None"
            self.t_labels = ", ".join(torrent.labels) if len(torrent.labels) > 0 else "None"

            self.t_status = torrent.status.title()
            self.t_location = torrent.download_dir
            self.t_downloaded = Util.print_size(torrent.downloaded_ever)
            self.t_uploaded = Util.print_size(torrent.uploaded_ever)
            self.t_ratio = f'{torrent.ratio:.2f}'
            self.t_error = torrent.error_string if torrent.error_string else "None"

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
                              'Yes' if f.selected else 'No',
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
                              Util.get_country(p["address"]),
                              p["address"],
                              p["clientName"])

            table = self.query_one("#trackers")
            table.clear()

            for t in self.r_torrent.tracker_stats:
                table.add_row(t.host,
                              # Transmission RPC numbers tiers from 0
                              t.tier + 1,
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

    @log_time
    def action_view_list(self):
        self.post_message(self.TorrentViewClosed())

    @log_time
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

    @log_time
    def action_go_right(self):
        tabs = self.query_one(TabbedContent)
        active = tabs.active

        if active == 'tab-overview':
            tabs.active = 'tab-files'
        elif active == 'tab-files':
            tabs.active = 'tab-peers'
        elif active == 'tab-peers':
            tabs.active = 'tab-trackers'

    @log_time
    def action_scroll_up(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").scroll_up()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").scroll_up()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()

    @log_time
    def action_scroll_down(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").scroll_down()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").scroll_down()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()

    @log_time
    def action_scroll_top(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").action_scroll_top()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").action_scroll_top()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()

    @log_time
    def action_scroll_bottom(self):
        if self.query_one(TabbedContent).active == 'tab-files':
            self.query_one("#files").action_scroll_bottom()
        elif self.query_one(TabbedContent).active == 'tab-peers':
            self.query_one("#peers").action_scroll_bottom()
        elif self.query_one(TabbedContent).active == 'tab-trackers':
            self.query_one("#trackers").scroll_up()


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
        def __init__(self, torrent):
            super().__init__()
            self.torrent = torrent

    class OpenSortOrder(Message):
        pass

    class AddTorrent(Message):
        def __init__(self, value: str, is_link: bool) -> None:
            super().__init__()
            self.value = value
            self.is_link = is_link

    class TorrentLabelsUpdated(Message):
        def __init__(self, torrent, value: str) -> None:
            super().__init__()
            self.torrent = torrent
            self.value = value

    class SortOrderSelected(Message):
        def __init__(self, order: str, is_asc: bool) -> None:
            super().__init__()
            self.order = order
            self.is_asc = is_asc

    class PageChanged(Message):
        def __init__(self, state: PageState) -> None:
            super().__init__()
            self.state = state

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("t", "toggle_alt_speed", "Toggle alt speed"),
            Binding("S", "show_statistics", "Show statistics"),

            Binding('"', "screenshot", "Save screenshot"),

            Binding("d", "toggle_dark", "Toggle dark mode", priority=True),
            Binding("?", "help", "Snow help"),
            Binding("q", "quit", "Quit", priority=True),
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
                    ConfirmationDialog(message=event.message,
                                       description=event.description),
                    event.check_quit)

    @log_time
    @on(OpenAddTorrent)
    def handle_open_add_torrent(self, event: OpenAddTorrent) -> None:
        self.push_screen(AddTorrentDialog(self.r_tsession.session))

    @log_time
    @on(OpenUpdateTorrentLabels)
    def handle_open_update_torrent_labels(self, event: OpenUpdateTorrentLabels) -> None:
        self.push_screen(UpdateTorrentLabelsDialog(event.torrent))

    @log_time
    @on(OpenSortOrder)
    def handle_open_sort_order(self, event: OpenSortOrder) -> None:
        self.push_screen(SortOrderDialog())

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
    @on(TorrentLabelsUpdated)
    def handle_torrent_labels_updated(self, event: TorrentLabelsUpdated) -> None:
        labels = [x.strip() for x in event.value.split(',') if x.strip()]

        if len(labels) > 0:
            self.client.change_torrent(event.torrent.id,
                                       labels=labels)

            self.post_message(MainApp.Notification(
                f"Updated torrent labels:\n{','.join(labels)}"))
        else:
            self.client.change_torrent(event.torrent.id,
                                       labels=[])
            self.post_message(MainApp.Notification(
                "Removed torrent labels"))

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

    app = MainApp(host=args.host, port=args.port,
                  username=args.username, password=args.password,
                  view_mode=args.view_mode,
                  refresh_interval=args.refresh_interval,
                  page_size=args.page_size,
                  limit_torrents=args.limit_torrents,
                  version=tewi_version)
    app.run()


if __name__ == "__main__":
    cli()
