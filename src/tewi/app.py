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
import sys

from datetime import datetime

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import ContentSwitcher

from .common import sort_orders, TorrentDTO
from .service import create_client, ClientError
from .message import AddTorrentCommand, TorrentLabelsUpdatedEvent, SortOrderUpdatedEvent, Notification, Confirm, \
        OpenSortOrderCommand, OpenSearchCommand, PageChangedEvent, VerifyTorrentCommand, ReannounceTorrentCommand, \
        OpenTorrentInfoCommand, OpenTorrentListCommand, OpenAddTorrentCommand, ToggleTorrentCommand, \
        RemoveTorrentCommand, TorrentRemovedEvent, TrashTorrentCommand, TorrentTrashedEvent, SearchCompletedEvent, \
        StartAllTorrentsCommand, StopAllTorrentsCommand, OpenUpdateTorrentLabelsCommand
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
from .ui.panel.listview import TorrentListViewPanel
from .ui.panel.details import TorrentInfoPanel


logger = logging.getLogger('tewi')


# Core UI panels


class MainApp(App):

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("t", "toggle_alt_speed", "[Speed] Toggle limits"),
            Binding("S", "show_statistics", "[Info] Statistics"),
            Binding("P", "show_preferences", "[App] Preferences"),

            Binding('"', "screenshot", "[App] Screenshot"),

            Binding("d", "toggle_dark", "[UI] Toggle theme", priority=True),
            Binding("?", "help", "[App] Help"),
            Binding("q", "quit", "[App] Quit", priority=True),
            ]

    r_torrents: list[TorrentDTO] | None = reactive(None)
    r_session = reactive(None)
    r_page = reactive(None)

    @log_time
    def __init__(self, client_type: str, host: str, port: str,
                 username: str, password: str,
                 view_mode: str,
                 refresh_interval: int,
                 page_size: int,
                 limit_torrents: int,
                 test_mode: int,
                 version: str):

        super().__init__()

        self.title = 'Tewi'

        self.view_mode = view_mode
        self.refresh_interval = refresh_interval
        self.limit_torrents = limit_torrents
        self.page_size = page_size
        self.test_mode = test_mode

        self.tewi_version = version

        self.c_type = client_type
        self.c_host = host
        self.c_port = port

        self.client = create_client(client_type=self.c_type,
                                    host=self.c_host,
                                    port=self.c_port,
                                    username=username,
                                    password=password)

        self.sort_order = sort_orders[0]
        self.sort_order_asc = True

    @log_time
    def compose(self) -> ComposeResult:
        yield InfoPanel(self.tewi_version,
                        self.client.meta()['name'],
                        self.client.meta()['version'],
                        self.c_host,
                        self.c_port)

        with Horizontal():
            with ContentSwitcher(initial="torrent-list"):
                yield TorrentListViewPanel(id="torrent-list",
                                           page_size=self.page_size,
                                           view_mode=self.view_mode).data_bind(r_torrents=MainApp.r_torrents)
                yield TorrentInfoPanel(has_separate_id=self.client.has_separate_id(), id="torrent-info")

        yield StatePanel().data_bind(r_session=MainApp.r_session,
                                     r_page=MainApp.r_page)

    @log_time
    def on_mount(self) -> None:
        self.load_tdata()
        self.set_interval(self.refresh_interval, self.load_tdata)

    @log_time
    @work(exclusive=True, thread=True)
    async def load_tdata(self) -> None:
        logging.info("Start loading data from torrent client...")

        torrents = self.client.torrents_test(self.test_mode) if self.test_mode else self.client.torrents()
        session = self.client.session(torrents, self.sort_order, self.sort_order_asc)

        torrents.sort(key=self.sort_order.sort_func,
                      reverse=not self.sort_order_asc)

        self.call_from_thread(self.set_tdata, torrents, session)

    @log_time
    def set_tdata(self, torrents: list[TorrentDTO], session) -> None:
        self.r_torrents = torrents
        self.r_session = session

    @log_time
    def action_toggle_alt_speed(self) -> None:
        alt_speed_enabled = self.client.toggle_alt_speed()

        if alt_speed_enabled:
            self.post_message(Notification("Turtle Mode enabled"))
        else:
            self.post_message(Notification("Turtle Mode disabled"))

    @log_time
    def action_show_statistics(self) -> None:
        self.push_screen(StatisticsDialog(self.client.stats()))

    @log_time
    def action_show_preferences(self) -> None:
        self.push_screen(PreferencesDialog(self.client.preferences()))

    @log_time
    def action_help(self) -> None:
        self.push_screen(HelpDialog(self.screen.active_bindings.values()))

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
    @on(OpenSortOrderCommand)
    def handle_open_sort_order_command(self, event: OpenSortOrderCommand) -> None:
        self.push_screen(SortOrderDialog())

    @log_time
    @on(OpenSearchCommand)
    def handle_open_search(self, event: OpenSearchCommand) -> None:
        self.push_screen(SearchDialog())

    @log_time
    @on(AddTorrentCommand)
    def handle_add_torrent_command(self, event: AddTorrentCommand) -> None:
        try:
            self.client.add_torrent(event.value)
            self.post_message(Notification("New torrent was added"))
        except ClientError as e:
            self.post_message(Notification(
                f"Failed to add torrent:\n{e}",
                "warning"))
        except FileNotFoundError:
            self.post_message(Notification(
                f"Failed to add torrent:\nFile not found {event.value}",
                "warning"))

    @log_time
    @on(OpenUpdateTorrentLabelsCommand)
    def handle_open_update_torrent_labels_command(self, event: OpenUpdateTorrentLabelsCommand) -> None:
        self.push_screen(UpdateTorrentLabelsDialog(event.torrent, None))

    @log_time
    @on(VerifyTorrentCommand)
    def handle_verify_torrent_command(self, event: VerifyTorrentCommand) -> None:
        self.client.verify_torrent(event.torrent_id)
        self.post_message(Notification("Torrent sent to verification"))

    @log_time
    @on(ReannounceTorrentCommand)
    def handle_reannounce_torrent_command(self, event: ReannounceTorrentCommand) -> None:
        self.client.reannounce_torrent(event.torrent_id)
        self.post_message(Notification("Torrent reannounce started"))

    @log_time
    @on(SearchCompletedEvent)
    def handle_search_completed_event(self, event: SearchCompletedEvent) -> None:
        self.query_one(TorrentListViewPanel).search_torrent(event.search_term)

    @log_time
    @on(TorrentLabelsUpdatedEvent)
    def handle_torrent_labels_updated_event(self, event: TorrentLabelsUpdatedEvent) -> None:
        labels = [x.strip() for x in event.value.split(',') if x.strip()]

        if len(event.torrent_ids) == 1:
            count_label = '1 torrent'
        else:
            count_label = f"{len(event.torrent_ids)} torrents"

        if len(labels) > 0:
            self.client.update_labels(event.torrent_ids, labels)

            self.post_message(Notification(
                f"Updated torrent labels ({count_label}):\n{','.join(labels)}"))
        else:
            self.client.update_labels(event.torrent_ids, [])

            self.post_message(Notification(
                f"Removed torrent labels ({count_label})"))

    @log_time
    @on(SortOrderUpdatedEvent)
    def handle_sort_order_updated_event(self, event: SortOrderUpdatedEvent) -> None:
        self.sort_order = event.order
        self.sort_order_asc = event.is_asc

        direction = 'ASC' if event.is_asc else 'DESC'
        self.post_message(Notification(
            f"Selected sort order: {event.order.name} {direction}"))

    @log_time
    @on(PageChangedEvent)
    def handle_page_changed_event(self, event: PageChangedEvent) -> None:
        self.r_page = event.state

    # refactored

    @log_time
    @on(OpenTorrentInfoCommand)
    def handle_open_torrent_info_command(self, event: OpenTorrentInfoCommand) -> None:
        torrent = self.client.torrent(event.torrent_id)

        self.query_one(ContentSwitcher).current = "torrent-info"
        self.query_one(TorrentInfoPanel).r_torrent = torrent

    @log_time
    @on(OpenTorrentListCommand)
    def handle_open_torrent_list_command(self, event: OpenTorrentListCommand) -> None:
        self.query_one(ContentSwitcher).current = "torrent-list"

    @log_time
    @on(OpenAddTorrentCommand)
    def handle_open_add_torrent_command(self, event: OpenAddTorrentCommand) -> None:
        session = self.client.session(self.r_torrents, self.sort_order, self.sort_order_asc)
        self.push_screen(AddTorrentDialog(session['download_dir'],
                                          session['download_dir_free_space']))

    @log_time
    @on(ToggleTorrentCommand)
    def handle_toggle_torrent_command(self, event: ToggleTorrentCommand) -> None:
        if event.torrent_status == 'stopped':
            self.client.start_torrent(event.torrent_id)
            self.post_message(Notification("Torrent started"))
        else:
            self.client.stop_torrent(event.torrent_id)
            self.post_message(Notification("Torrent stopped"))

    @log_time
    @on(RemoveTorrentCommand)
    def handle_remove_torrent_command(self, event: RemoveTorrentCommand) -> None:
        def check_quit(confirmed: bool | None) -> None:
            if confirmed:
                self.client.remove_torrent(event.torrent_id,
                                           delete_data=False)

                self.query_one(TorrentListViewPanel).post_message(TorrentRemovedEvent(event.torrent_id))
                self.post_message(Notification("Torrent removed"))

        message = "Remove torrent?"
        description = ("Once removed, continuing the "
                       "transfer will require the torrent file. "
                       "Are you sure you want to remove it?")

        self.post_message(Confirm(message=message,
                                  description=description,
                                  check_quit=check_quit))

    @log_time
    @on(TrashTorrentCommand)
    def handle_trash_torrent_command(self, event: TrashTorrentCommand) -> None:
        def check_quit(confirmed: bool | None) -> None:
            if confirmed:
                self.client.remove_torrent(event.torrent_id,
                                           delete_data=True)

                self.query_one(TorrentListViewPanel).post_message(TorrentTrashedEvent(event.torrent_id))
                self.post_message(Notification("Torrent and its data removed"))

        message = "Remove torrent and delete data?"
        description = ("All data downloaded for this torrent "
                       "will be deleted. Are you sure you "
                       "want to remove it?")

        self.post_message(Confirm(message=message,
                                  description=description,
                                  check_quit=check_quit))

    @log_time
    @on(StartAllTorrentsCommand)
    def handle_start_all_torrents_command(self, event: StartAllTorrentsCommand) -> None:
        self.client.start_all_torrents()
        self.post_message(Notification("All torrents started"))

    @log_time
    @on(StopAllTorrentsCommand)
    def handle_stop_all_torrents_command(self, event: StopAllTorrentsCommand) -> None:
        self.client.stop_all_torrents()
        self.post_message(Notification("All torrents stopped"))


@log_time
def create_app():
    """Create and return a MainApp instance. Used by `textual run` for development."""
    tewi_version = __version__

    parser = argparse.ArgumentParser(
            prog='tewi',
            description='Text-based interface for BitTorrent clients (Transmission and qBittorrent)',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--client-type', type=str, default='transmission',
                        choices=['transmission', 'qbittorrent'],
                        help='Type of BitTorrent client to connect to')
    parser.add_argument('--view-mode', type=str, default='card',
                        choices=['card', 'compact', 'oneline'],
                        help='View mode for torrents in list')
    parser.add_argument('--refresh-interval', type=int, default=5,
                        help='Refresh interval (in seconds) for loading data from daemon')
    parser.add_argument('--limit-torrents', type=int, default=None,
                        help='Limit number of displayed torrents (useful for performance debugging)')
    parser.add_argument('--page-size', type=int, default=30,
                        help='Number of torrents displayed per page')
    parser.add_argument('--host', type=str, default='localhost',
                        help='BitTorrent daemon host for connection')
    parser.add_argument('--port', type=str, default='9091',
                        help='BitTorrent daemon port for connection')
    parser.add_argument('--username', type=str,
                        help='BitTorrent daemon username for connection')
    parser.add_argument('--password', type=str,
                        help='BitTorrent daemon password for connection')
    parser.add_argument('--logs', default=False,
                        action=argparse.BooleanOptionalAction,
                        help='Enable verbose logs (added to `tewi.log` file)')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + tewi_version,
                        help='Show version and exit')
    parser.add_argument('-a', '--add-torrent', type=str, metavar='PATH_OR_MAGNET',
                        help='Add torrent from file path or magnet link and exit')
    parser.add_argument('--test-mode', type=int, default=None,
                        help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.logs:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging.basicConfig(
                filename=(f'tewi_{now}.log'),
                encoding='utf-8',
                format='%(asctime)s.%(msecs)03d %(module)-15s %(levelname)-8s %(message)s',
                level=logging.DEBUG,
                datefmt='%Y-%m-%d %H:%M:%S')

    logger.info(f'Start Tewi {tewi_version}...')
    logger.info(f'Loaded CLI options: {args}')

    # Handle add-torrent mode (non-interactive)
    if args.add_torrent:
        try:
            client = create_client(client_type=args.client_type,
                                   host=args.host,
                                   port=args.port,
                                   username=args.username,
                                   password=args.password)
            client.add_torrent(args.add_torrent)
            print(f"Successfully added torrent to {args.client_type} daemon at {args.host}:{args.port}")
            sys.exit(0)
        except ClientError as e:
            print(f"Failed to add torrent: {e}", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print(f"Failed to add torrent: File not found {args.add_torrent}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Failed to add torrent: {e}", file=sys.stderr)
            sys.exit(1)

    # Create and return the app instance
    try:
        app = MainApp(client_type=args.client_type,
                      host=args.host, port=args.port,
                      username=args.username, password=args.password,
                      view_mode=args.view_mode,
                      refresh_interval=args.refresh_interval,
                      page_size=args.page_size,
                      limit_torrents=args.limit_torrents,
                      test_mode=args.test_mode,
                      version=tewi_version)
        return app
    except ClientError as e:
        print(f"Failed to connect to {args.client_type} daemon at {args.host}:{args.port}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize application: {e}", file=sys.stderr)
        sys.exit(1)


@log_time
def cli():
    """CLI entry point. Creates and runs the MainApp."""
    app = create_app()
    app.run()


if __name__ == "__main__":
    cli()
