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


class TransmissionData:
    def __init__(self, session, session_stats, torrents):
        self.session = session
        self.session_stats = session_stats
        self.torrents = torrents


class ReactiveLabel(Label):

    name = reactive(str | None)

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
            with ContentSwitcher(initial="main-panel"):
                yield ScrollableContainer(id="torrent-list")
                yield ScrollableContainer(id="torrent-info")

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

        self.log(f'Load session from Transmission: {vars(tdata.session)}')
        self.log(f'Load session_stats from Transmission: {vars(tdata.session_stats)}')
        self.log(f'Load {len(tdata.torrents)} torrents from Transmission')

        self.r_tdata = tdata


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
