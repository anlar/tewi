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


class MainApp(App):

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("q", "quit", "Quit"),
            ]

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
