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

from .common import get_filter_by_id, sort_orders, TorrentDTO
from .config import TrackSetAction, get_config_path, load_config, create_default_config, \
    merge_config_with_args, get_available_profiles
from .service import create_client, ClientError
from .message import AddTorrentCommand, TorrentLabelsUpdatedEvent, SortOrderUpdatedEvent, Notification, Confirm, \
        OpenSortOrderCommand, OpenFilterCommand, FilterUpdatedEvent, OpenSearchCommand, PageChangedEvent, \
        VerifyTorrentCommand, ReannounceTorrentCommand, \
        OpenTorrentInfoCommand, OpenTorrentListCommand, OpenAddTorrentCommand, ToggleTorrentCommand, \
        RemoveTorrentCommand, TorrentRemovedEvent, TrashTorrentCommand, TorrentTrashedEvent, SearchCompletedEvent, \
        StartAllTorrentsCommand, StopAllTorrentsCommand, OpenUpdateTorrentLabelsCommand, \
        AddTorrentFromWebSearchCommand, WebSearchQuerySubmitted, ChangeTorrentPriorityCommand, \
        ToggleFileDownloadCommand, OpenEditTorrentCommand, EditTorrentCommand, SearchStateChangedEvent, \
        OpenUpdateTorrentCategoryCommand, UpdateTorrentCategoryCommand
from .util.decorator import log_time
from .ui.dialog.confirm import ConfirmDialog
from .ui.dialog.help import HelpDialog
from .ui.dialog.preferences import PreferencesDialog
from .ui.dialog.statistics import StatisticsDialog
from .ui.dialog.torrent.add import AddTorrentDialog
from .ui.dialog.torrent.category import UpdateTorrentCategoryDialog
from .ui.dialog.torrent.edit import EditTorrentDialog
from .ui.dialog.torrent.label import UpdateTorrentLabelsDialog
from .ui.dialog.torrent.search import SearchDialog
from .ui.dialog.torrent.filter import FilterDialog
from .ui.dialog.torrent.sort import SortOrderDialog
from .ui.dialog.websearch_query import WebSearchQueryDialog
from .ui.panel.info import InfoPanel
from .ui.panel.state import StatePanel
from .ui.panel.listview import TorrentListViewPanel
from .ui.panel.details import TorrentInfoPanel
from .ui.panel.websearch import TorrentWebSearch

from .service.search.search import SearchClient, print_available_providers


logger = logging.getLogger('tewi')


# Core UI panels


class MainApp(App):

    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("t", "toggle_alt_speed", "[Speed] Toggle limits"),
            Binding("S", "show_statistics", "[Info] Statistics"),
            Binding("P", "show_preferences", "[App] Preferences"),

            Binding("W", "open_websearch", "[Search] Web search"),

            Binding('"', "screenshot", "[App] Screenshot", priority=True),

            Binding("d", "toggle_dark", "[UI] Toggle theme"),
            Binding("?", "help", "[App] Help"),
            Binding("q", "quit", "[App] Quit", priority=True),
            ]

    r_torrents: list[TorrentDTO] | None = reactive(None)
    r_session = reactive(None)
    r_page = reactive(None)
    r_search = reactive(None)

    last_search_query = None

    @log_time
    def __init__(self, client_type: str, host: str, port: str,
                 username: str, password: str,
                 view_mode: str,
                 refresh_interval: int,
                 page_size: int,
                 limit_torrents: int,
                 test_mode: int,
                 version: str,
                 jackett_url: str,
                 jackett_api_key: str,
                 search_query: str,
                 filter: str,
                 badge_max_count: int,
                 badge_max_length: int,
                 search_providers: str | None = None):

        super().__init__()

        self.title = 'Tewi'

        self.view_mode = view_mode
        self.refresh_interval = refresh_interval
        self.limit_torrents = limit_torrents
        self.page_size = page_size
        self.test_mode = test_mode
        self.badge_max_count = badge_max_count
        self.badge_max_length = badge_max_length

        self.tewi_version = version
        self.initial_search_query = search_query
        self.jackett_url = jackett_url
        self.jackett_api_key = jackett_api_key

        self.c_type = client_type
        self.c_host = host
        self.c_port = port

        self.client = create_client(client_type=self.c_type,
                                    host=self.c_host,
                                    port=self.c_port,
                                    username=username,
                                    password=password)

        self.search = SearchClient(jackett_url, jackett_api_key,
                                   search_providers)

        self.sort_order = sort_orders[0]
        self.sort_order_asc = True
        self.filter_option = get_filter_by_id(filter)

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
                                           view_mode=self.view_mode,
                                           capability_set_priority=self.client.capable('set_priority'),
                                           capability_label=self.client.capable('label'),
                                           capability_category=self.client.capable('category')
                                           ).data_bind(r_torrents=MainApp.r_torrents)
                yield TorrentInfoPanel(capability_torrent_id=self.client.capable('torrent_id'), id="torrent-info")
                yield TorrentWebSearch(
                    jackett_url=self.jackett_url,
                    jackett_api_key=self.jackett_api_key,
                    id="torrent-websearch"
                )

        yield StatePanel().data_bind(r_session=MainApp.r_session,
                                     r_page=MainApp.r_page,
                                     r_search=MainApp.r_search)

    @log_time
    def on_mount(self) -> None:
        self.load_tdata()
        self.set_interval(self.refresh_interval, self.load_tdata)

        # Auto-start web search if query provided via CLI
        if self.initial_search_query:
            self.post_message(WebSearchQuerySubmitted(
                self.initial_search_query))

        self.query_one(TorrentListViewPanel).focus()

    @log_time
    @work(exclusive=True, thread=True)
    async def load_tdata(self) -> None:
        current_pane = self.query_one(ContentSwitcher).current
        if current_pane == 'torrent-list':
            logging.info("Start loading data from torrent client...")

            if self.test_mode:
                torrents = self.client.torrents_test(self.test_mode)
            else:
                torrents = self.client.torrents()

            # Load session with full list of torrents (before filtering)
            session = self.client.session(torrents, self.sort_order,
                                          self.sort_order_asc,
                                          self.filter_option)

            torrents = [t for t in torrents
                        if self.filter_option.filter_func(t)]

            # Add filtered count to session for display
            session['filtered_torrents_count'] = len(torrents)

            torrents.sort(key=self.sort_order.sort_func,
                          reverse=not self.sort_order_asc)

            self.call_from_thread(self.set_tdata, torrents, session)
        elif current_pane == 'torrent-info':
            info_panel = self.query_one(TorrentInfoPanel)
            torrent = self.client.torrent(info_panel.r_torrent.id)
            self.call_from_thread(self.set_tdata2, torrent)

    @log_time
    def set_tdata2(self, torrent: TorrentDTO) -> None:
        self.query_one(TorrentInfoPanel).r_torrent = torrent

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
    def action_open_websearch(self) -> None:
        self.push_screen(WebSearchQueryDialog(self.last_search_query))

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
    @on(OpenFilterCommand)
    def handle_open_filter_command(self, event: OpenFilterCommand) -> None:
        self.push_screen(FilterDialog())

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
    @on(OpenEditTorrentCommand)
    def handle_open_edit_torrent_command(self, event: OpenEditTorrentCommand) -> None:
        self.push_screen(EditTorrentDialog(event.torrent))

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
    @on(ChangeTorrentPriorityCommand)
    def handle_change_torrent_priority_command(self, event: ChangeTorrentPriorityCommand) -> None:
        # Cycle through priorities: None/0 -> 1 (high) -> -1 (low) -> 0 (normal) -> 1 (high)...
        if event.current_priority is None or event.current_priority == 0:
            new_priority = 1
            priority_label = "High"
        elif event.current_priority == 1:
            new_priority = -1
            priority_label = "Low"
        else:  # -1
            new_priority = 0
            priority_label = "Normal"

        self.client.set_priority(event.torrent_id, new_priority)
        self.post_message(Notification(f"Torrent priority set to {priority_label}"))

    @log_time
    @on(ToggleFileDownloadCommand)
    def handle_toggle_file_download_command(self, event: ToggleFileDownloadCommand) -> None:
        self.client.set_file_priority(event.torrent_id, event.file_ids, event.priority)
        # Refresh torrent details to show updated file priorities
        torrent = self.client.torrent(event.torrent_id)
        self.query_one(TorrentInfoPanel).r_torrent = torrent

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
    @on(EditTorrentCommand)
    def handle_edit_torrent_command(self, event: EditTorrentCommand) -> None:
        try:
            self.client.edit_torrent(event.torrent_id, event.name,
                                     event.location)
            self.post_message(Notification("Torrent updated successfully"))
        except Exception as e:
            self.post_message(Notification(
                f"Failed to update torrent: {str(e)}", "error"))

    @log_time
    @on(OpenUpdateTorrentCategoryCommand)
    def handle_open_update_torrent_category_command(self, event: OpenUpdateTorrentCategoryCommand) -> None:
        categories = self.client.get_categories()
        self.push_screen(UpdateTorrentCategoryDialog(event.torrent, categories))

    @log_time
    @on(UpdateTorrentCategoryCommand)
    def handle_update_torrent_category_command(self, event: UpdateTorrentCategoryCommand) -> None:
        try:
            self.client.set_category(event.torrent_id, event.category)
            category_name = event.category if event.category else "None"
            self.post_message(Notification(f"Category set to: {category_name}"))
        except Exception as e:
            self.post_message(Notification(
                f"Failed to set category: {str(e)}", "error"))

    @log_time
    @on(SortOrderUpdatedEvent)
    def handle_sort_order_updated_event(self, event: SortOrderUpdatedEvent) -> None:
        self.sort_order = event.order
        self.sort_order_asc = event.is_asc

        direction = 'ASC' if event.is_asc else 'DESC'
        self.post_message(Notification(
            f"Selected sort order: {event.order.name} {direction}"))

    @log_time
    @on(FilterUpdatedEvent)
    def handle_filter_updated_event(self, event: FilterUpdatedEvent) -> None:
        self.filter_option = event.filter_option

        self.post_message(Notification(
            f"Selected filter: {event.filter_option.name}"))

    @log_time
    @on(PageChangedEvent)
    def handle_page_changed_event(self, event: PageChangedEvent) -> None:
        self.r_page = event.state

    @log_time
    @on(SearchStateChangedEvent)
    def handle_search_state_changed_event(self,
                                          event: SearchStateChangedEvent) -> None:

        if event.current and event.total:
            self.r_search = f" Found: {event.current} / {event.total} "
        else:
            self.r_search = None

    # refactored

    @log_time
    @on(OpenTorrentInfoCommand)
    def handle_open_torrent_info_command(self, event: OpenTorrentInfoCommand) -> None:
        torrent = self.client.torrent(event.torrent_id)

        self.query_one(ContentSwitcher).current = "torrent-info"
        self.query_one(TorrentInfoPanel).r_torrent = torrent
        # Ensure that correct tab is opened,
        # because tab panel stores previously selected tab.
        self.query_one(TorrentInfoPanel).open_default_tab()

    @log_time
    @on(OpenTorrentListCommand)
    def handle_open_torrent_list_command(self, event: OpenTorrentListCommand) -> None:
        self.query_one(ContentSwitcher).current = "torrent-list"
        # Focus on the torrent list when returning from other panels
        self.query_one(TorrentListViewPanel).focus()

    @log_time
    @on(OpenAddTorrentCommand)
    def handle_open_add_torrent_command(self, event: OpenAddTorrentCommand) -> None:
        session = self.client.session(self.r_torrents, self.sort_order,
                                      self.sort_order_asc, self.filter_option)
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
    @on(WebSearchQuerySubmitted)
    def handle_websearch_query_submitted(self, event: WebSearchQuerySubmitted) -> None:
        # Save executed search query to use it as default value on next search
        self.last_search_query = event.query
        # Switch to results panel
        self.query_one(ContentSwitcher).current = "torrent-websearch"
        # Execute search with query and selected indexers
        self.query_one(TorrentWebSearch).execute_search(
            event.query, event.selected_indexers, event.selected_categories)

    @log_time
    @on(AddTorrentFromWebSearchCommand)
    def handle_add_torrent_from_websearch_command(self, event: AddTorrentFromWebSearchCommand) -> None:
        try:
            self.client.add_torrent(event.magnet_link)
            self.post_message(Notification("New torrent was added from web search"))
        except ClientError as e:
            self.post_message(Notification(
                f"Failed to add torrent:\n{e}",
                "warning"))

    def check_action(self, action: str,
                     parameters: tuple[object, ...]) -> bool | None:
        """Check if an action may run."""
        if action == "toggle_alt_speed":
            return self.client.capable("toggle_alt_speed")

        return True


def _setup_argument_parser(version: str) -> argparse.ArgumentParser:
    """Set up and return the argument parser."""
    p = argparse.ArgumentParser(
            prog='tewi',
            description='Text-based interface for BitTorrent clients '
                        '(Transmission, qBittorrent, and Deluge)',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Actions
    p.add_argument('-a', '--add-torrent', type=str,
                   metavar='PATH_OR_MAGNET',
                   help='Add torrent from file path or magnet link and exit')
    p.add_argument('-s', '--search', type=str,
                   metavar='QUERY',
                   help='Start web search with the given query')
    p.add_argument('--create-config',
                   action='store_true',
                   help='Create default configuration file and exit')

    # Client
    p.add_argument('--client-type', type=str, default='transmission',
                   choices=['transmission', 'qbittorrent', 'deluge'],
                   action=TrackSetAction,
                   help='Type of BitTorrent client to connect to')
    p.add_argument('--host', type=str, default='localhost',
                   action=TrackSetAction,
                   help='BitTorrent daemon host for connection')
    p.add_argument('--port', type=str, default='9091',
                   action=TrackSetAction,
                   help='BitTorrent daemon port for connection')
    p.add_argument('--username', type=str,
                   action=TrackSetAction,
                   help='BitTorrent daemon username for connection')
    p.add_argument('--password', type=str,
                   action=TrackSetAction,
                   help='BitTorrent daemon password for connection')

    # UI
    p.add_argument('--view-mode', type=str, default='card',
                   choices=['card', 'compact', 'oneline'],
                   action=TrackSetAction,
                   help='View mode for torrents in list')
    p.add_argument('--page-size', type=int, default=30,
                   action=TrackSetAction,
                   help='Number of torrents displayed per page')
    p.add_argument('--filter', type=str, default='all',
                   choices=['all', 'active', 'downloading',
                            'seeding', 'paused', 'finished'],
                   action=TrackSetAction,
                   help='Filter torrents by status')
    p.add_argument('--badge-max-count', type=int, default=3,
                   action=TrackSetAction,
                   help='Maximum number of badges (category and labels) '
                   'to display (-1: unlimited, 0: none, 1+: count)')
    p.add_argument('--badge-max-length', type=int, default=10,
                   action=TrackSetAction,
                   help='Maximum length of badge (category or label) text'
                   '(0: unlimited, 1+: truncate with …)')
    p.add_argument('--refresh-interval', type=int, default=5,
                   action=TrackSetAction,
                   help='Refresh interval (in seconds) for loading '
                   'data from daemon')

    # Search
    p.add_argument('--jackett-url', type=str, default='http://localhost:9117',
                   action=TrackSetAction,
                   help='URL of your Jackett instance')
    p.add_argument('--jackett-api-key', type=str,
                   action=TrackSetAction,
                   help='API key for Jackett authentication')
    p.add_argument('--search-providers', type=str,
                   action=TrackSetAction,
                   help='Comma-separated list of enabled search providers '
                   '(tpb, torrentscsv, yts, nyaa, jackett). '
                   'Leave empty to enable all')
    p.add_argument('--list-search-providers', action='store_true',
                   help='List available search providers and exit')

    # Profiles
    p.add_argument('--profile', type=str,
                   action=TrackSetAction,
                   help='Load configuration profile from tewi-PROFILE.conf')
    p.add_argument('--profiles', action='store_true',
                   help='List available configuration profiles and exit')

    # Other
    p.add_argument('--logs', default=False,
                   action=argparse.BooleanOptionalAction,
                   help='Enable verbose logs (saved to `tewi_TS.log` file)')
    p.add_argument('--version', action='version',
                   version='%(prog)s ' + version,
                   help='Show version and exit')

    # Hidden
    p.add_argument('--limit-torrents', type=int, default=None,
                   help=argparse.SUPPRESS)
    p.add_argument('--test-mode', type=int, default=None,
                   help=argparse.SUPPRESS)

    return p


def _handle_add_torrent_mode(args) -> None:
    """Handle non-interactive add-torrent mode."""
    try:
        client = create_client(client_type=args.client_type,
                               host=args.host,
                               port=args.port,
                               username=args.username,
                               password=args.password)
        client.add_torrent(args.add_torrent)
        print(f"Successfully added torrent to {args.client_type} daemon "
              f"at {args.host}:{args.port}")
        sys.exit(0)
    except ClientError as e:
        print(f"Failed to add torrent: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Failed to add torrent: File not found "
              f"{args.add_torrent}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to add torrent: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_profiles_command():
    """Handle --profiles command to list available profiles."""
    profiles = get_available_profiles()
    if profiles:
        print("Available profiles:")
        for profile in profiles:
            print(f"  - {profile}")
    else:
        print("No profiles found")
    sys.exit(0)


def _handle_list_search_providers_command():
    """Handle --list-search-providers command."""
    print_available_providers()
    sys.exit(0)


def _handle_create_config_command(profile: str | None):
    """Handle --create-config command to create config file."""
    config_path = get_config_path(profile)
    create_default_config(config_path)
    if profile:
        print(f"Profile config file created: {config_path}")
    else:
        print(f"Config file created: {config_path}")
    sys.exit(0)


@log_time
def _handle_commands(args) -> None:
    # Handle --list-search-providers (list providers and exit)
    if args.list_search_providers:
        _handle_list_search_providers_command()

    # Handle --profiles (list available profiles and exit)
    if args.profiles:
        _handle_profiles_command()

    # Handle --create-config (must happen before other processing)
    if args.create_config:
        _handle_create_config_command(getattr(args, 'profile', None))


@log_time
def create_app():
    """Create and return a MainApp instance."""
    tewi_version = __version__

    parser = _setup_argument_parser(tewi_version)
    args = parser.parse_args()

    _handle_commands(args)

    # Load config file and merge with CLI arguments
    profile = getattr(args, 'profile', None)
    config = load_config(profile)
    merge_config_with_args(config, args)

    if args.logs:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging.basicConfig(
                filename=(f'tewi_{now}.log'),
                encoding='utf-8',
                format='%(asctime)s.%(msecs)03d %(module)-15s '
                       '%(levelname)-8s %(message)s',
                level=logging.DEBUG,
                datefmt='%Y-%m-%d %H:%M:%S')

    logger.info(f'Start Tewi {tewi_version}...')
    logger.info(f'Loaded CLI options: {args}')

    # Validate search query if provided
    if args.search:
        query = args.search.strip()
        if not query:
            print("Error: Search query cannot be empty", file=sys.stderr)
            sys.exit(1)
        args.search = query

    # Handle add-torrent mode (non-interactive)
    if args.add_torrent:
        _handle_add_torrent_mode(args)

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
                      version=tewi_version,
                      jackett_url=args.jackett_url,
                      jackett_api_key=args.jackett_api_key,
                      search_query=args.search,
                      filter=args.filter,
                      badge_max_count=args.badge_max_count,
                      badge_max_length=args.badge_max_length,
                      search_providers=getattr(args, 'search_providers',
                                               None))
        return app
    except ClientError as e:
        print(f"Failed to connect to {args.client_type} daemon at "
              f"{args.host}:{args.port}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize application: {e}", file=sys.stderr)
        sys.exit(1)


@log_time
def cli():
    """CLI entry point. Creates and runs the MainApp."""

    # set terminal title
    print('\33]0;Tewi\a', end='', flush=True)

    app = create_app()
    app.run()

    # clean terminal title
    print('\33]0;\a', end='', flush=True)


if __name__ == "__main__":
    cli()
