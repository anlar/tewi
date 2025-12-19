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
import sys

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import ContentSwitcher

from .config import (
    TrackSetAction,
    create_default_config,
    get_available_profiles,
    get_config_path,
    load_config,
    merge_config_with_args,
)
from .search.manager import SearchClient, print_available_providers
from .torrent.factory import ClientCapability, create_client
from .torrent.models import ClientError, Torrent
from .ui.dialog.confirm import ConfirmDialog
from .ui.dialog.help import HelpDialog
from .ui.dialog.preferences import PreferencesDialog
from .ui.dialog.search.query import WebSearchQueryDialog
from .ui.dialog.statistics import StatisticsDialog
from .ui.dialog.torrent.add import AddTorrentDialog
from .ui.dialog.torrent.category import UpdateTorrentCategoryDialog
from .ui.dialog.torrent.edit import EditTorrentDialog
from .ui.dialog.torrent.filter import FilterDialog
from .ui.dialog.torrent.label import UpdateTorrentLabelsDialog
from .ui.dialog.torrent.search import SearchDialog
from .ui.dialog.torrent.sort import SortOrderDialog
from .ui.messages import (
    AddTorrentCommand,
    AddTorrentFromWebSearchCommand,
    ChangeTorrentPriorityCommand,
    Confirm,
    EditTorrentCommand,
    FilterUpdatedEvent,
    Notification,
    OpenAddTorrentCommand,
    OpenEditTorrentCommand,
    OpenFilterCommand,
    OpenSearchCommand,
    OpenSortOrderCommand,
    OpenTorrentInfoCommand,
    OpenTorrentListCommand,
    OpenUpdateTorrentCategoryCommand,
    OpenUpdateTorrentLabelsCommand,
    PageChangedEvent,
    ReannounceTorrentCommand,
    RemoveTorrentCommand,
    SearchCompletedEvent,
    SearchStateChangedEvent,
    SortOrderUpdatedEvent,
    StartAllTorrentsCommand,
    StopAllTorrentsCommand,
    ToggleFileDownloadCommand,
    ToggleTorrentCommand,
    TorrentLabelsUpdatedEvent,
    TorrentRemovedEvent,
    TorrentTrashedEvent,
    TrashTorrentCommand,
    UpdateTorrentCategoryCommand,
    VerifyTorrentCommand,
    WebSearchQuerySubmitted,
)
from .ui.models import FilterState, get_filter_by_id, sort_orders
from .ui.panel.details import TorrentInfoPanel
from .ui.panel.info import InfoPanel
from .ui.panel.listview import TorrentListViewPanel
from .ui.panel.state import StatePanel
from .ui.panel.websearch import TorrentWebSearch
from .util.log import get_logger, init_logger, log_time
from .version import __version__

logger = get_logger()


# Core UI panels


class MainApp(App):
    ENABLE_COMMAND_PALETTE = False

    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("t", "toggle_alt_speed", "[Speed] Toggle limits"),
        Binding("S", "show_statistics", "[Info] Statistics"),
        Binding("P", "show_preferences", "[App] Preferences"),
        Binding("w", "open_websearch_clean", "[Search] Web search (clean)"),
        Binding("W", "open_websearch", "[Search] Web search"),
        Binding('"', "screenshot", "[App] Screenshot", priority=True),
        Binding("d", "toggle_dark", "[UI] Toggle theme"),
        Binding("?", "help", "[App] Help"),
        Binding("q", "quit", "[App] Quit", priority=True),
    ]

    r_torrents: list[Torrent] | None = reactive(None)
    r_session = reactive(None)
    r_page = reactive(None)
    r_search = reactive(None)

    r_sort_order = reactive(sort_orders[0])
    r_sort_order_asc = reactive(True)
    r_filter_state = reactive(None)

    last_search_query = None
    last_search_indexers = None
    last_search_categories = None

    @log_time
    def __init__(
        self,
        client_type: str,
        host: str,
        port: str,
        path: str,
        username: str,
        password: str,
        view_mode: str,
        refresh_interval: int,
        page_size: int,
        limit_torrents: int,
        test_mode: int,
        version: str,
        jackett_url: str,
        jackett_api_key: str,
        jackett_multi: bool,
        prowlarr_url: str,
        prowlarr_api_key: str,
        prowlarr_multi: bool,
        bitmagnet_url: str,
        search_query: str,
        filter: str,
        badge_max_count: int,
        badge_max_length: int,
        search_providers: list[str] | None = None,
    ):
        super().__init__()

        logger.info(f"Initializing Tewi application v{version}")
        logger.info(f"Client configuration: {client_type} at {host}:{port}")

        self.title = "Tewi"

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
        self.prowlarr_url = prowlarr_url
        self.prowlarr_api_key = prowlarr_api_key

        self.c_type = client_type
        self.c_host = host
        self.c_port = port

        self.client = create_client(
            client_type=self.c_type,
            host=self.c_host,
            port=self.c_port,
            path=path,
            username=username,
            password=password,
        )

        self.search = SearchClient(
            jackett_url,
            jackett_api_key,
            jackett_multi,
            prowlarr_url,
            prowlarr_api_key,
            prowlarr_multi,
            bitmagnet_url,
            search_providers,
        )

        self.filter_option = get_filter_by_id(filter)
        self.r_filter_state = FilterState(self.filter_option, 0)

        logger.info("Application initialization completed")

    @log_time
    def compose(self) -> ComposeResult:
        logger.info("Composing UI components")
        yield InfoPanel(
            self.tewi_version,
            self.client.meta()["name"],
            self.client.meta()["version"],
            self.c_host,
            self.c_port,
        )

        with Horizontal():
            with ContentSwitcher(initial="torrent-list"):
                yield TorrentListViewPanel(
                    id="torrent-list",
                    page_size=self.page_size,
                    view_mode=self.view_mode,
                    capability_set_priority=self.client.capable(
                        ClientCapability.SET_PRIORITY
                    ),
                    capability_label=self.client.capable(
                        ClientCapability.LABEL
                    ),
                    capability_category=self.client.capable(
                        ClientCapability.CATEGORY
                    ),
                ).data_bind(r_torrents=MainApp.r_torrents)
                yield TorrentInfoPanel(
                    capability_torrent_id=self.client.capable(
                        ClientCapability.TORRENT_ID
                    ),
                    id="torrent-info",
                )
                yield TorrentWebSearch(id="torrent-websearch")

        yield StatePanel().data_bind(
            r_session=MainApp.r_session,
            r_sort_order=MainApp.r_sort_order,
            r_sort_order_asc=MainApp.r_sort_order_asc,
            r_filter_state=MainApp.r_filter_state,
            r_page=MainApp.r_page,
            r_search=MainApp.r_search,
        )

    @log_time
    def on_mount(self) -> None:
        logger.info("Application mounted, starting initial data load")
        self.load_tdata()
        logger.info(f"Setting up refresh interval: {self.refresh_interval}s")
        self.set_interval(self.refresh_interval, self.load_tdata)

        # Auto-start web search if query provided via CLI
        if self.initial_search_query:
            logger.info(
                f"Auto-starting web search with query: "
                f"{self.initial_search_query}"
            )
            self.post_message(
                WebSearchQuerySubmitted(self.initial_search_query)
            )

        self.query_one(TorrentListViewPanel).focus()
        logger.info("Application startup completed")

    @log_time
    def on_unmount(self) -> None:
        logger.info("Tewi application shutdown")

    @log_time
    @work(exclusive=True, thread=True)
    async def load_tdata(self) -> None:
        logger.debug("Start loading data from torrent client...")

        current_pane = self.query_one(ContentSwitcher).current

        if current_pane == "torrent-list":
            if self.test_mode:
                torrents = self.client.torrents_test(self.test_mode)
            else:
                torrents = self.client.torrents()

            # Load session with full list of torrents (before filtering)
            session = self.client.session(torrents)

            torrents = [
                t for t in torrents if self.filter_option.filter_func(t)
            ]

            filter_state = FilterState(self.filter_option, len(torrents))

            torrents.sort(
                key=self.r_sort_order.sort_func,
                reverse=not self.r_sort_order_asc,
            )

            logger.info(f"Loaded {len(torrents)} torrents from client")

            self.call_from_thread(
                self.set_tdata_list, torrents, session, filter_state
            )
        elif current_pane == "torrent-info":
            info_panel = self.query_one(TorrentInfoPanel)
            torrent = self.client.torrent(info_panel.r_torrent.hash)

            logger.info(f"Loaded torrent ID = {torrent.id} from client")

            self.call_from_thread(self.set_tdata_info, torrent)

    @log_time
    def set_tdata_info(self, torrent: Torrent) -> None:
        self.query_one(TorrentInfoPanel).r_torrent = torrent

    @log_time
    def set_tdata_list(
        self, torrents: list[Torrent], session, filter_state: FilterState
    ) -> None:
        self.r_torrents = torrents
        self.r_session = session
        self.r_filter_state = filter_state

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
    def action_open_websearch_clean(self) -> None:
        """Open web search dialog with clean state (no pre-filled data)."""
        self.push_screen(WebSearchQueryDialog())

    @log_time
    def action_open_websearch(self) -> None:
        """Open web search dialog with last search query and selections."""
        self.push_screen(
            WebSearchQueryDialog(
                self.last_search_query,
                self.last_search_indexers,
                self.last_search_categories,
            )
        )

    @log_time
    @on(Notification)
    def handle_notification(self, event: Notification) -> None:
        timeout = 3 if event.severity == "information" else 5

        self.notify(
            message=event.message, severity=event.severity, timeout=timeout
        )

    @log_time
    @on(Confirm)
    def handle_confirm(self, event: Confirm) -> None:
        self.push_screen(
            ConfirmDialog(message=event.message, description=event.description),
            event.check_quit,
        )

    @log_time
    @on(OpenSortOrderCommand)
    def handle_open_sort_order_command(
        self, event: OpenSortOrderCommand
    ) -> None:
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
            self.post_message(
                Notification(f"Failed to add torrent:\n{e}", "warning")
            )
        except FileNotFoundError:
            self.post_message(
                Notification(
                    f"Failed to add torrent:\nFile not found {event.value}",
                    "warning",
                )
            )

    @log_time
    @on(OpenUpdateTorrentLabelsCommand)
    def handle_open_update_torrent_labels_command(
        self, event: OpenUpdateTorrentLabelsCommand
    ) -> None:
        self.push_screen(UpdateTorrentLabelsDialog(event.torrent, None))

    @log_time
    @on(OpenEditTorrentCommand)
    def handle_open_edit_torrent_command(
        self, event: OpenEditTorrentCommand
    ) -> None:
        self.push_screen(EditTorrentDialog(event.torrent))

    @log_time
    @on(VerifyTorrentCommand)
    def handle_verify_torrent_command(
        self, event: VerifyTorrentCommand
    ) -> None:
        self.client.verify_torrent(event.torrent_hash)
        self.post_message(Notification("Torrent sent to verification"))

    @log_time
    @on(ReannounceTorrentCommand)
    def handle_reannounce_torrent_command(
        self, event: ReannounceTorrentCommand
    ) -> None:
        self.client.reannounce_torrent(event.torrent_hash)
        self.post_message(Notification("Torrent reannounce started"))

    @log_time
    @on(ChangeTorrentPriorityCommand)
    def handle_change_torrent_priority_command(
        self, event: ChangeTorrentPriorityCommand
    ) -> None:
        # Cycle: None/0 -> 1 (high) -> -1 (low) -> 0 (normal) -> 1...
        if event.current_priority is None or event.current_priority == 0:
            new_priority = 1
            priority_label = "High"
        elif event.current_priority == 1:
            new_priority = -1
            priority_label = "Low"
        else:  # -1
            new_priority = 0
            priority_label = "Normal"

        self.client.set_priority(event.torrent_hash, new_priority)
        self.post_message(
            Notification(f"Torrent priority set to {priority_label}")
        )

    @log_time
    @on(ToggleFileDownloadCommand)
    def handle_toggle_file_download_command(
        self, event: ToggleFileDownloadCommand
    ) -> None:
        self.client.set_file_priority(
            event.torrent_hash, event.file_ids, event.priority
        )
        # Refresh torrent details to show updated file priorities
        torrent = self.client.torrent(event.torrent_hash)
        self.query_one(TorrentInfoPanel).r_torrent = torrent

    @log_time
    @on(SearchCompletedEvent)
    def handle_search_completed_event(
        self, event: SearchCompletedEvent
    ) -> None:
        self.query_one(TorrentListViewPanel).search_torrent(event.search_term)

    @log_time
    @on(TorrentLabelsUpdatedEvent)
    def handle_torrent_labels_updated_event(
        self, event: TorrentLabelsUpdatedEvent
    ) -> None:
        labels = [x.strip() for x in event.value.split(",") if x.strip()]

        if len(event.torrent_hashes) == 1:
            count_label = "1 torrent"
        else:
            count_label = f"{len(event.torrent_hashes)} torrents"

        if len(labels) > 0:
            self.client.update_labels(event.torrent_hashes, labels)

            self.post_message(
                Notification(
                    f"Updated torrent labels ({count_label}):\n"
                    f"{','.join(labels)}"
                )
            )
        else:
            self.client.update_labels(event.torrent_hashes, [])

            self.post_message(
                Notification(f"Removed torrent labels ({count_label})")
            )

    @log_time
    @on(EditTorrentCommand)
    def handle_edit_torrent_command(self, event: EditTorrentCommand) -> None:
        try:
            self.client.edit_torrent(
                event.torrent_hash, event.name, event.location
            )
            self.post_message(Notification("Torrent updated successfully"))
        except Exception as e:
            self.post_message(
                Notification(f"Failed to update torrent: {str(e)}", "error")
            )

    @log_time
    @on(OpenUpdateTorrentCategoryCommand)
    def handle_open_update_torrent_category_command(
        self, event: OpenUpdateTorrentCategoryCommand
    ) -> None:
        categories = self.client.get_categories()
        self.push_screen(UpdateTorrentCategoryDialog(event.torrent, categories))

    @log_time
    @on(UpdateTorrentCategoryCommand)
    def handle_update_torrent_category_command(
        self, event: UpdateTorrentCategoryCommand
    ) -> None:
        try:
            self.client.set_category(event.torrent_hash, event.category)
            category_name = event.category if event.category else "None"
            self.post_message(Notification(f"Category set to: {category_name}"))
        except Exception as e:
            self.post_message(
                Notification(f"Failed to set category: {str(e)}", "error")
            )

    @log_time
    @on(SortOrderUpdatedEvent)
    def handle_sort_order_updated_event(
        self, event: SortOrderUpdatedEvent
    ) -> None:
        self.r_sort_order = event.order
        self.r_sort_order_asc = event.is_asc

        direction = "ASC" if event.is_asc else "DESC"
        self.post_message(
            Notification(f"Selected sort order: {event.order.name} {direction}")
        )

    @log_time
    @on(FilterUpdatedEvent)
    def handle_filter_updated_event(self, event: FilterUpdatedEvent) -> None:
        self.filter_option = event.filter_option

        self.post_message(
            Notification(f"Selected filter: {event.filter_option.name}")
        )

    @log_time
    @on(PageChangedEvent)
    def handle_page_changed_event(self, event: PageChangedEvent) -> None:
        self.r_page = event.state

    @log_time
    @on(SearchStateChangedEvent)
    def handle_search_state_changed_event(
        self, event: SearchStateChangedEvent
    ) -> None:
        if event.current and event.total:
            self.r_search = f" Found: {event.current} / {event.total} "
        else:
            self.r_search = None

    # refactored

    @log_time
    @on(OpenTorrentInfoCommand)
    def handle_open_torrent_info_command(
        self, event: OpenTorrentInfoCommand
    ) -> None:
        logger.info(
            f"Switching to torrent info view for hash: {event.torrent_hash}"
        )
        torrent = self.client.torrent(event.torrent_hash)

        self.query_one(ContentSwitcher).current = "torrent-info"
        self.query_one(TorrentInfoPanel).r_torrent = torrent
        # Ensure that correct tab is opened,
        # because tab panel stores previously selected tab.
        self.query_one(TorrentInfoPanel).open_default_tab()

    @log_time
    @on(OpenTorrentListCommand)
    def handle_open_torrent_list_command(
        self, event: OpenTorrentListCommand
    ) -> None:
        logger.info("Switching to torrent list view")
        self.query_one(ContentSwitcher).current = "torrent-list"
        # Focus on the torrent list when returning from other panels
        self.query_one(TorrentListViewPanel).focus()

    @log_time
    @on(OpenAddTorrentCommand)
    def handle_open_add_torrent_command(
        self, event: OpenAddTorrentCommand
    ) -> None:
        session = self.client.session(self.r_torrents)
        self.push_screen(
            AddTorrentDialog(
                session["download_dir"], session["download_dir_free_space"]
            )
        )

    @log_time
    @on(ToggleTorrentCommand)
    def handle_toggle_torrent_command(
        self, event: ToggleTorrentCommand
    ) -> None:
        if event.torrent_status == "stopped":
            self.client.start_torrent(event.torrent_hash)
            self.post_message(Notification("Torrent started"))
        else:
            self.client.stop_torrent(event.torrent_hash)
            self.post_message(Notification("Torrent stopped"))

    @log_time
    @on(RemoveTorrentCommand)
    def handle_remove_torrent_command(
        self, event: RemoveTorrentCommand
    ) -> None:
        def check_quit(confirmed: bool | None) -> None:
            if confirmed:
                self.client.remove_torrent(
                    event.torrent_hash, delete_data=False
                )

                self.query_one(TorrentListViewPanel).post_message(
                    TorrentRemovedEvent(event.torrent_hash)
                )
                self.post_message(Notification("Torrent removed"))

        message = "Remove torrent?"
        description = (
            "Once removed, continuing the "
            "transfer will require the torrent file. "
            "Are you sure you want to remove it?"
        )

        self.post_message(
            Confirm(
                message=message, description=description, check_quit=check_quit
            )
        )

    @log_time
    @on(TrashTorrentCommand)
    def handle_trash_torrent_command(self, event: TrashTorrentCommand) -> None:
        def check_quit(confirmed: bool | None) -> None:
            if confirmed:
                self.client.remove_torrent(event.torrent_hash, delete_data=True)

                self.query_one(TorrentListViewPanel).post_message(
                    TorrentTrashedEvent(event.torrent_hash)
                )
                self.post_message(Notification("Torrent and its data removed"))

        message = "Remove torrent and delete data?"
        description = (
            "All data downloaded for this torrent "
            "will be deleted. Are you sure you "
            "want to remove it?"
        )

        self.post_message(
            Confirm(
                message=message, description=description, check_quit=check_quit
            )
        )

    @log_time
    @on(StartAllTorrentsCommand)
    def handle_start_all_torrents_command(
        self, event: StartAllTorrentsCommand
    ) -> None:
        self.client.start_all_torrents()
        self.post_message(Notification("All torrents started"))

    @log_time
    @on(StopAllTorrentsCommand)
    def handle_stop_all_torrents_command(
        self, event: StopAllTorrentsCommand
    ) -> None:
        self.client.stop_all_torrents()
        self.post_message(Notification("All torrents stopped"))

    @log_time
    @on(WebSearchQuerySubmitted)
    def handle_websearch_query_submitted(
        self, event: WebSearchQuerySubmitted
    ) -> None:
        logger.info(f"Starting web search with query: '{event.query}'")
        # Save executed search parameters to use on next search
        self.last_search_query = event.query
        self.last_search_indexers = event.selected_indexers
        self.last_search_categories = event.selected_categories
        # Switch to results panel
        logger.info("Switching to web search results view")
        self.query_one(ContentSwitcher).current = "torrent-websearch"
        # Execute search with query and selected indexers
        self.query_one(TorrentWebSearch).execute_search(
            event.query, event.selected_indexers, event.selected_categories
        )

    @log_time
    @on(AddTorrentFromWebSearchCommand)
    def handle_add_torrent_from_websearch_command(
        self, event: AddTorrentFromWebSearchCommand
    ) -> None:
        try:
            self.client.add_torrent(event.magnet_link)
            self.post_message(
                Notification("New torrent was added from web search")
            )
        except ClientError as e:
            self.post_message(
                Notification(f"Failed to add torrent:\n{e}", "warning")
            )

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:
        """Check if an action may run."""
        if action == "toggle_alt_speed":
            return self.client.capable(ClientCapability.TOGGLE_ALT_SPEED)

        return True


def _setup_argument_parser(version: str) -> argparse.ArgumentParser:
    """Set up and return the argument parser."""
    p = argparse.ArgumentParser(
        prog="tewi",
        description="Text-based interface for BitTorrent clients "
        "(Transmission, qBittorrent, and Deluge)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Actions
    p.add_argument(
        "-a",
        "--add-torrent",
        type=str,
        metavar="PATH_OR_MAGNET",
        help="Add torrent from file path or magnet link and exit",
    )
    p.add_argument(
        "-s",
        "--search",
        type=str,
        metavar="QUERY",
        help="Start web search with the given query",
    )
    p.add_argument(
        "--create-config",
        action="store_true",
        help="Create default configuration file and exit",
    )

    # Client
    p.add_argument(
        "--client-type",
        type=str,
        default="transmission",
        choices=["transmission", "qbittorrent", "deluge"],
        action=TrackSetAction,
        help="Type of BitTorrent client to connect to",
    )
    p.add_argument(
        "--host",
        type=str,
        default="localhost",
        action=TrackSetAction,
        help="BitTorrent daemon host for connection",
    )
    p.add_argument(
        "--port",
        type=str,
        default="9091",
        action=TrackSetAction,
        help="BitTorrent daemon port for connection",
    )
    p.add_argument(
        "--path",
        type=str,
        action=TrackSetAction,
        help="RPC path for Transmission (default: /transmission/rpc) "
        "or base JSON path for Deluge (default: /json)",
    )
    p.add_argument(
        "--username",
        type=str,
        action=TrackSetAction,
        help="BitTorrent daemon username for connection",
    )
    p.add_argument(
        "--password",
        type=str,
        action=TrackSetAction,
        help="BitTorrent daemon password for connection",
    )

    # UI
    p.add_argument(
        "--view-mode",
        type=str,
        default="card",
        choices=["card", "compact", "oneline"],
        action=TrackSetAction,
        help="View mode for torrents in list",
    )
    p.add_argument(
        "--page-size",
        type=int,
        default=30,
        action=TrackSetAction,
        help="Number of torrents displayed per page",
    )
    p.add_argument(
        "--filter",
        type=str,
        default="all",
        choices=[
            "all",
            "active",
            "downloading",
            "seeding",
            "paused",
            "finished",
        ],
        action=TrackSetAction,
        help="Filter torrents by status",
    )
    p.add_argument(
        "--badge-max-count",
        type=int,
        default=3,
        action=TrackSetAction,
        help="Maximum number of badges (category and labels) "
        "to display (-1: unlimited, 0: none, 1+: count)",
    )
    p.add_argument(
        "--badge-max-length",
        type=int,
        default=10,
        action=TrackSetAction,
        help="Maximum length of badge (category or label) text"
        "(0: unlimited, 1+: truncate with …)",
    )
    p.add_argument(
        "--refresh-interval",
        type=int,
        default=5,
        action=TrackSetAction,
        help="Refresh interval (in seconds) for loading data from daemon",
    )

    # Search
    p.add_argument(
        "--jackett-url",
        type=str,
        default="http://localhost:9117",
        action=TrackSetAction,
        help="URL of your Jackett instance",
    )
    p.add_argument(
        "--jackett-api-key",
        type=str,
        action=TrackSetAction,
        help="API key for Jackett authentication",
    )
    p.add_argument(
        "--jackett-multi",
        action="store_true",
        default=False,
        help="Enable multi-indexer mode: load all Jackett indexers "
        "individually in search dialog (default: use single 'all' endpoint)",
    )
    p.add_argument(
        "--prowlarr-url",
        type=str,
        default="http://localhost:9696",
        action=TrackSetAction,
        help="URL of your Prowlarr instance",
    )
    p.add_argument(
        "--prowlarr-api-key",
        type=str,
        default="http://localhost:3333",
        action=TrackSetAction,
        help="API key for Prowlarr authentication",
    )
    p.add_argument(
        "--prowlarr-multi",
        action="store_true",
        default=False,
        help="Enable multi-indexer mode: load all Prowlarr indexers "
        "individually in search dialog (default: use single 'all' endpoint)",
    )
    p.add_argument(
        "--bitmagnet-url",
        type=str,
        action=TrackSetAction,
        help="URL of your Bitmagnet instance",
    )
    p.add_argument(
        "--search-providers",
        type=str,
        nargs="*",
        choices=[
            "tpb",
            "yts",
            "nyaa",
            "torrentscsv",
            "jackett",
            "prowlarr",
            "bitmagnet",
            "torrentz2",
        ],
        default=["tpb", "yts", "nyaa", "torrentscsv", "torrentz2"],
        action=TrackSetAction,
        help="Space-separated list of enabled search providers. "
        "Order matters: first providers take priority when deduplicating",
    )
    p.add_argument(
        "--list-search-providers",
        action="store_true",
        help="List available search providers and exit",
    )

    # Profiles
    p.add_argument(
        "--profile",
        type=str,
        action=TrackSetAction,
        help="Load configuration profile from tewi-PROFILE.conf",
    )
    p.add_argument(
        "--profiles",
        action="store_true",
        help="List available configuration profiles and exit",
    )

    # Other
    p.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        action=TrackSetAction,
        help="Set logging level",
    )
    p.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + version,
        help="Show version and exit",
    )

    # Hidden
    p.add_argument(
        "--limit-torrents", type=int, default=None, help=argparse.SUPPRESS
    )
    p.add_argument(
        "--test-mode", type=int, default=None, help=argparse.SUPPRESS
    )

    return p


def _handle_add_torrent_mode(args) -> None:
    """Handle non-interactive add-torrent mode."""
    try:
        client = create_client(
            client_type=args.client_type,
            host=args.host,
            port=args.port,
            path=args.path,
            username=args.username,
            password=args.password,
        )
        client.add_torrent(args.add_torrent)
        print(
            f"Successfully added torrent to {args.client_type} daemon "
            f"at {args.host}:{args.port}"
        )
        sys.exit(0)
    except ClientError as e:
        print(f"Failed to add torrent: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"Failed to add torrent: File not found {args.add_torrent}",
            file=sys.stderr,
        )
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
        logger.info("Listing available search providers")
        _handle_list_search_providers_command()

    # Handle --profiles (list available profiles and exit)
    if args.profiles:
        logger.info("Listing available configuration profiles")
        _handle_profiles_command()

    # Handle --create-config (must happen before other processing)
    if args.create_config:
        logger.info("Creating default configuration file")
        _handle_create_config_command(getattr(args, "profile", None))


@log_time
def create_app():
    """Create and return a MainApp instance."""
    tewi_version = __version__

    parser = _setup_argument_parser(tewi_version)
    args = parser.parse_args()

    _handle_commands(args)

    # Load config file and merge with CLI arguments
    profile = getattr(args, "profile", None)
    config = load_config(profile)
    merge_config_with_args(config, args)

    # Initialize logging
    init_logger(args.log_level)

    logger.info(f"Start Tewi {tewi_version}...")
    if profile:
        logger.info(f"Using configuration profile: {profile}")
    logger.info(f"Loaded CLI options: {args}")

    # Validate search query if provided
    if args.search:
        query = args.search.strip()
        if not query:
            print("Error: Search query cannot be empty", file=sys.stderr)
            sys.exit(1)
        args.search = query

    # Handle add-torrent mode (non-interactive)
    if args.add_torrent:
        logger.info(f"Running in add-torrent mode: {args.add_torrent}")
        _handle_add_torrent_mode(args)

    # Create and return the app instance
    try:
        app = MainApp(
            client_type=args.client_type,
            host=args.host,
            port=args.port,
            path=args.path,
            username=args.username,
            password=args.password,
            view_mode=args.view_mode,
            refresh_interval=args.refresh_interval,
            page_size=args.page_size,
            limit_torrents=args.limit_torrents,
            test_mode=args.test_mode,
            version=tewi_version,
            jackett_url=args.jackett_url,
            jackett_api_key=args.jackett_api_key,
            jackett_multi=args.jackett_multi,
            prowlarr_url=args.prowlarr_url,
            prowlarr_api_key=args.prowlarr_api_key,
            prowlarr_multi=args.prowlarr_multi,
            bitmagnet_url=args.bitmagnet_url,
            search_query=args.search,
            filter=args.filter,
            badge_max_count=args.badge_max_count,
            badge_max_length=args.badge_max_length,
            search_providers=getattr(args, "search_providers", None),
        )
        return app
    except ClientError as e:
        print(
            f"Failed to connect to {args.client_type} daemon at "
            f"{args.host}:{args.port}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize application: {e}", file=sys.stderr)
        sys.exit(1)


@log_time
def cli():
    """CLI entry point. Creates and runs the MainApp."""

    # set terminal title
    print("\33]0;Tewi\a", end="", flush=True)

    app = create_app()
    logger.info("Starting Tewi application")
    try:
        app.run()
    finally:
        # clean terminal title
        print("\33]0;\a", end="", flush=True)


if __name__ == "__main__":
    cli()
