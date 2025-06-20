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

import argparse
import logging
import os
import pathlib
import sys

from transmission_rpc import Client
from transmission_rpc.error import TransmissionError


from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import ContentSwitcher

from .common import TransmissionSession, sort_orders
from .message import AddTorrent, TorrentLabelsUpdated, SearchTorrent, SortOrderSelected, Notification, Confirm, \
        OpenAddTorrent, OpenUpdateTorrentLabels, OpenSortOrder, OpenSearch, OpenPreferences, PageChanged
from .util.decorator import log_time
from .ui.dialog.confirm import ConfirmDialog
from .ui.dialog.help import HelpDialog
from .ui.dialog.preferences import PreferencesDialog
from .ui.dialog.statistics import StatisticsDialog
from .ui.dialog.torrent.add import AddTorrentDialog
from .ui.dialog.torrent.label import UpdateTorrentLabelsDialog
from .ui.dialog.torrent.search import SearchDialog
from .ui.dialog.torrent.sort import SortOrderDialog
from .ui.panel.info import InfoPanel
from .ui.panel.state import StatePanel
from .ui.panel.list import TorrentListPanel
from .ui.panel.details import TorrentInfoPanel


logger = logging.getLogger('tewi')


# Core UI panels


class MainApp(App):

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
