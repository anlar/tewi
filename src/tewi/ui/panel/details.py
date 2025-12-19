import os
import platform
import subprocess
from datetime import datetime
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.reactive import reactive
from textual.widgets import Static, TabbedContent, TabPane
from textual.widgets.data_table import RowKey

from ...torrent.models import TorrentFile, TorrentFilePriority
from ...util.geoip import get_country
from ...util.log import log_time
from ..messages import OpenTorrentListCommand, ToggleFileDownloadCommand
from ..util import (
    print_size,
    print_speed,
    print_time_ago,
    subtitle_keys,
)
from ..widget.common import ReactiveLabel, VimDataTable


class TorrentInfoPanel(ScrollableContainer):
    BINDINGS = [
        Binding(
            "o,1", "open_tab('tab-overview')", "[Navigation] Open Overview"
        ),
        Binding("f,2", "open_tab('tab-files')", "[Navigation] Open Files"),
        Binding("p,3", "open_tab('tab-peers')", "[Navigation] Open Peers"),
        Binding(
            "t,4", "open_tab('tab-trackers')", "[Navigation] Open Trackers"
        ),
        Binding(
            "enter",
            "open_file",
            "[Files] Open file",
            priority=True,
        ),
        Binding(
            "space",
            "toggle_file_download(None)",
            "[Files] Toggle file download",
        ),
        Binding(
            "H",
            "toggle_file_download('high')",
            "[Files] Set High file priority",
        ),
        Binding(
            "M",
            "toggle_file_download('medium')",
            "[Files] Set Medium file priority",
        ),
        Binding(
            "L", "toggle_file_download('low')", "[Files] Set Low file priority"
        ),
        Binding("x,esc", "close", "[Navigation] Close"),
    ]

    @log_time
    def __init__(self, capability_torrent_id: bool, **kwargs):
        super().__init__(**kwargs)
        self.capability_torrent_id = capability_torrent_id
        self.file_count = 0
        self.file_list = []

        self.color_priority_low = self.app.current_theme.accent
        self.color_priority_high = self.app.current_theme.error

        # Build priority display mapping
        self.priority_display = {
            TorrentFilePriority.NOT_DOWNLOADING: "[dim]-[/]",
            TorrentFilePriority.LOW: f"[dim {self.color_priority_low}]↓[/]",
            TorrentFilePriority.MEDIUM: "→",
            TorrentFilePriority.HIGH: f"[bold {self.color_priority_high}]↑[/]",
        }

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
    t_category = reactive(None)

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
        self.border_subtitle = subtitle_keys(
            ("1/O", "Overview"),
            ("2/F", "Files"),
            ("3/P", "Peers"),
            ("4/T", "Trackers"),
            ("X", "Close"),
        )
        with TabbedContent():
            with TabPane("[u]O[/]verview", id="tab-overview"):
                with ScrollableContainer(id="overview"):
                    with Vertical():
                        with Container(classes="overview-block") as block:
                            block.border_title = "Details"

                            yield Static("Name:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_name
                            )
                            # Only show ID if client has separate ID field
                            # (not same as hash)
                            if self.capability_torrent_id:
                                yield Static("ID:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_id
                                )
                            yield Static("Hash:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_hash
                            )

                            yield Static("Size:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_size
                            )
                            yield Static("Files:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_files
                            )
                            yield Static("Pieces:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_pieces
                            )
                            yield Static("Privacy:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_privacy
                            )

                            yield Static("Comment:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_comment
                            )
                            yield Static("Creator:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_creator
                            )
                            yield Static("Labels:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_labels
                            )
                            yield Static("Category:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_category
                            )
                            yield Static("Location:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_location
                            )
                            yield Static("Error:", classes="name")
                            yield ReactiveLabel().data_bind(
                                name=TorrentInfoPanel.t_error
                            )

                        with Horizontal(classes="overview-bottom"):
                            # Should be the largest block in the bottom row
                            # for all other blocks to use height=100% to
                            # maximize their heights, that is why it is
                            # missing 'overview-small-block' CSS class
                            # State panel - 25% width
                            with Container(
                                classes="overview-block state-panel"
                            ) as block:
                                block.border_title = "State"

                                yield Static("Status:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_status
                                )
                                yield Static("Downloaded:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_downloaded
                                )
                                yield Static("Uploaded:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_uploaded
                                )
                                yield Static("Ratio:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_ratio
                                )

                            with Container(
                                classes="overview-block overview-small-block "
                                "dates-panel"
                            ) as block:
                                block.border_title = "Dates"

                                yield Static("Added:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_date_added
                                )
                                yield Static("Started:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_date_started
                                )
                                yield Static("Completed:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_date_completed
                                )
                                yield Static("Last active:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_date_active
                                )

                            with Container(
                                classes="overview-block overview-small-block "
                                "peers-panel"
                            ) as block:
                                block.border_title = "Peers"

                                yield Static("Active:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_peers_active
                                )
                                yield Static("Seeding:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_peers_up
                                )
                                yield Static("Downloading:", classes="name")
                                yield ReactiveLabel().data_bind(
                                    name=TorrentInfoPanel.t_peers_down
                                )

            with TabPane("[u]F[/]iles", id="tab-files"):
                with Container():
                    yield VimDataTable(
                        id="files", cursor_type="row", zebra_stripes=True
                    )

            with TabPane("[u]P[/]eers", id="tab-peers"):
                with Container():
                    yield VimDataTable(
                        id="peers", cursor_type="row", zebra_stripes=True
                    )

            with TabPane("[u]T[/]rackers", id="tab-trackers"):
                with Container():
                    yield VimDataTable(
                        id="trackers", cursor_type="row", zebra_stripes=True
                    )

    @log_time
    def on_mount(self):
        table = self.query_one("#files")
        table.add_columns(
            ("ID", "ID"),
            ("Size", "Size"),
            ("Done", "Done"),
            ("P", "P"),
            ("Name", "Name"),
        )

        table = self.query_one("#peers")
        table.add_columns(
            "Encrypted",
            "Up",
            "Down",
            "UL State",
            "DL State",
            "Progress",
            "Connection",
            "Direction",
            "Status",
            "Country",
            "Address",
            "Port",
            "Client",
        )

        table = self.query_one("#trackers")
        table.add_columns(
            "Tier",
            "Host",
            "Status",
            "P",
            "S",
            "L",
            "DL",
            "Announced",
            "Next",
            "Scraped",
            "Next",
            "Message",
        )

    @log_time
    def watch_r_torrent(self, new_r_torrent):
        if new_r_torrent:
            torrent = new_r_torrent

            self.t_id = str(torrent.id) if torrent.id else None
            self.t_hash = torrent.hash_string
            self.t_name = torrent.name
            self.t_size = print_size(torrent.total_size)
            self.t_files = str(len(torrent.files))
            piece_size = print_size(torrent.piece_size, size_bytes=1024)
            self.t_pieces = f"{torrent.piece_count} @ {piece_size}"

            if torrent.is_private:
                self.t_privacy = (
                    "Private to this tracker -- DHT and PEX disabled"
                )
            else:
                self.t_privacy = "Public torrent"

            self.t_comment = torrent.comment if torrent.comment else "None"
            self.t_creator = torrent.creator if torrent.creator else "None"
            self.t_labels = (
                ", ".join(torrent.labels) if len(torrent.labels) > 0 else "None"
            )
            self.t_category = torrent.category if torrent.category else "None"

            self.t_status = torrent.status.title()
            self.t_location = torrent.download_dir
            self.t_downloaded = print_size(torrent.downloaded_ever)
            self.t_uploaded = print_size(torrent.uploaded_ever)
            self.t_ratio = f"{torrent.ratio:.2f}"
            self.t_error = (
                torrent.error_string if torrent.error_string else "None"
            )

            self.t_date_added = self.print_datetime(torrent.added_date)
            self.t_date_started = self.print_datetime(torrent.start_date)
            self.t_date_completed = self.print_datetime(torrent.done_date)
            self.t_date_active = self.print_datetime(torrent.activity_date)

            self.t_peers_active = str(torrent.peers_connected)
            self.t_peers_up = str(torrent.peers_sending_to_us)
            self.t_peers_down = str(torrent.peers_getting_from_us)

            table = self.query_one("#files")

            # Store for toggle action
            self.file_list = self.get_file_list(
                self.r_torrent.files, self.priority_display
            )

            if self.file_count != len(self.file_list):
                table.clear()
                self.draw_file_table(table, self.file_list)
            else:
                self.update_file_table(table, self.file_list)

            self.file_count = len(self.file_list)

            table = self.query_one("#peers")
            selected_row = self.selected_row(table)
            table.clear()

            for p in self.r_torrent.peers:
                progress = p.progress * 100
                table.add_row(
                    "-"
                    if p.is_encrypted is None
                    else ("Yes" if p.is_encrypted else "No"),
                    print_speed(
                        p.rate_to_peer, print_secs=True, dash_for_zero=True
                    ),
                    print_speed(
                        p.rate_to_client, print_secs=True, dash_for_zero=True
                    ),
                    p.ul_state.value,
                    p.dl_state.value,
                    f"{progress:.0f}%",
                    p.connection_type or "-",
                    p.direction or "-",
                    p.flag_str or "-",
                    p.country or (get_country(p.address) or "-"),
                    p.address,
                    self.print_count(p.port),
                    p.client_name,
                    key=p.address + str(p.port),
                )

            self.select_row(table, selected_row)

            table = self.query_one("#trackers")
            selected_row = self.selected_row(table)
            table.clear()

            for t in self.r_torrent.trackers:
                table.add_row(
                    self.print_count(t.tier),
                    t.host,
                    t.status or "-",
                    self.print_count(t.peer_count),
                    self.print_count(t.seeder_count),
                    self.print_count(t.leecher_count),
                    self.print_count(t.download_count),
                    self.print_tracker_datetime(t.last_announce),
                    self.print_tracker_next_time(t.next_announce),
                    self.print_tracker_datetime(t.last_scrape),
                    self.print_tracker_next_time(t.next_scrape),
                    t.message or "-",
                    key=t.host,
                )

            self.select_row(table, selected_row)

    def selected_row(self, table: VimDataTable) -> RowKey | None:
        """Return selected row key (or None) from table"""
        cursor_row = table.cursor_row
        # Check if cursor is at a valid position
        if (
            cursor_row is None
            or cursor_row < 0
            or cursor_row >= table.row_count
        ):
            return None

        return table.coordinate_to_cell_key((cursor_row, 0)).row_key

    def select_row(self, table: VimDataTable, row_key: RowKey) -> None:
        """Select row by its key if it present in table"""
        if row_key in table.rows:
            row = table.get_row_index(row_key)
            if row:
                table.move_cursor(row=row)

    @log_time
    def update_file_table(self, table, file_list) -> None:
        row_keys = list(table.rows.keys())

        for row_idx, item in enumerate(file_list):
            if row_idx >= len(row_keys):
                break

            row_key = row_keys[row_idx]

            # Apply dim styling for not-downloading files
            if item.get("file_priority") == TorrentFilePriority.NOT_DOWNLOADING:
                table.update_cell(row_key, "ID", f"[dim]{item['id']}[/dim]")
                table.update_cell(row_key, "Size", f"[dim]{item['size']}[/dim]")
                table.update_cell(row_key, "Done", f"[dim]{item['done']}[/dim]")
                table.update_cell(row_key, "P", item["priority"])
                table.update_cell(
                    row_key, "Name", f"[dim]{item['display_name']}[/dim]"
                )
            else:
                table.update_cell(row_key, "ID", item["id"])
                table.update_cell(row_key, "Size", item["size"])
                table.update_cell(row_key, "Done", item["done"])
                table.update_cell(row_key, "P", item["priority"])
                table.update_cell(row_key, "Name", item["display_name"])

    @log_time
    def draw_file_table(self, table, file_list) -> None:
        for item in file_list:
            # Apply dim styling for not-downloading files
            if item.get("file_priority") == TorrentFilePriority.NOT_DOWNLOADING:
                table.add_row(
                    f"[dim]{item['id']}[/dim]",
                    f"[dim]{item['size']}[/dim]",
                    f"[dim]{item['done']}[/dim]",
                    item["priority"],
                    f"[dim]{item['display_name']}[/dim]",
                )
            else:
                table.add_row(
                    item["id"],
                    item["size"],
                    item["done"],
                    item["priority"],
                    item["display_name"],
                )

    @log_time
    def print_count(self, value: int) -> int:
        return value if value is not None else "-"

    @log_time
    def print_datetime(self, value: datetime) -> str:
        if value:
            time_ago = print_time_ago(value)
            return f"{value.strftime('%Y-%m-%d %H:%M:%S')} ({time_ago})"
        else:
            return "Never"

    @log_time
    def print_tracker_datetime(self, value: datetime) -> str:
        """Format tracker datetime as 'HH:MM:SS (Xm)' or '-'."""
        if value:
            now = datetime.now()
            diff = now - value
            total_seconds = diff.total_seconds()

            # Calculate time ago in compact format
            if total_seconds < 60:
                ago = "<1m"
            elif total_seconds < 3600:
                minutes = int(total_seconds / 60)
                ago = f"{minutes}m"
            elif total_seconds < 86400:
                hours = int(total_seconds / 3600)
                ago = f"{hours}h"
            else:
                days = int(total_seconds / 86400)
                ago = f"{days}d"

            return f"{value.strftime('%H:%M:%S')} ({ago})"
        else:
            return "-"

    @log_time
    def print_tracker_next_time(self, value: datetime) -> str:
        """Format tracker next time as 'Xm' or '-'."""
        if value:
            now = datetime.now()
            delta = value - now
            total_seconds = delta.total_seconds()

            if total_seconds < 0:
                return "overdue"
            elif total_seconds < 60:
                return "<1m"
            elif total_seconds < 3600:
                minutes = int(total_seconds / 60)
                return f"{minutes}m"
            elif total_seconds < 86400:
                hours = int(total_seconds / 3600)
                return f"{hours}h"
            else:
                days = int(total_seconds / 86400)
                return f"{days}d"
        else:
            return "-"

    @log_time
    def action_open_tab(self, tab_id: str):
        self.query_one(TabbedContent).active = tab_id

    @log_time
    def action_close(self):
        self.post_message(OpenTorrentListCommand())

    @log_time
    def _get_folder_child_file_ids(self, folder_path: str) -> list[int]:
        """Collect all child file IDs using path-based detection.

        Args:
            folder_path: The folder path (e.g., "docs/api")

        Returns:
            List of file IDs that are children of this folder
        """
        file_ids = []
        # Use path prefix matching on the original file list
        folder_prefix = f"{folder_path}/"

        for file in self.r_torrent.files:
            if file.name.startswith(folder_prefix):
                file_ids.append(file.id)

        return file_ids

    @log_time
    def _determine_target_priority(
        self, file_ids: list[int]
    ) -> TorrentFilePriority:
        """Determine target priority by checking first file's current
        priority."""
        first_file = next(
            (f for f in self.r_torrent.files if f.id == file_ids[0]), None
        )
        if not first_file:
            return TorrentFilePriority.MEDIUM

        if first_file.priority == TorrentFilePriority.NOT_DOWNLOADING:
            return TorrentFilePriority.MEDIUM
        else:
            return TorrentFilePriority.NOT_DOWNLOADING

    @log_time
    def action_toggle_file_download(self, action_code: str | None):
        """Toggle download status for selected file or folder."""
        # Only handle if we're on the files tab
        if (
            self.active_tab_id() != "tab-files"
            or not self.r_torrent
            or not self.file_list
        ):
            return

        table = self.query_one("#files")
        cursor_row = table.cursor_row

        # Check if cursor is at a valid position
        if (
            cursor_row is None
            or cursor_row < 0
            or cursor_row >= len(self.file_list)
        ):
            return

        selected_item = self.file_list[cursor_row]

        # Collect file IDs to toggle
        if selected_item["is_file"]:
            file_ids = [selected_item["id"]]
        else:
            folder_path = selected_item.get("folder_path")
            if not folder_path:
                return  # No valid folder path
            file_ids = self._get_folder_child_file_ids(folder_path)

        if not file_ids:
            return

        match action_code:
            case "high":
                target_priority = TorrentFilePriority.HIGH
            case "medium":
                target_priority = TorrentFilePriority.MEDIUM
            case "low":
                target_priority = TorrentFilePriority.LOW
            case _:
                target_priority = self._determine_target_priority(file_ids)

        # Post command to toggle files
        self.post_message(
            ToggleFileDownloadCommand(
                torrent_hash=self.r_torrent.hash_string,
                file_ids=file_ids,
                priority=target_priority,
            )
        )

    @log_time
    def _open_file_with_system_app(self, file_path: str):
        """Open file using platform-specific default application."""
        system = platform.system()
        if system == "Linux":
            subprocess.Popen(["xdg-open", file_path])
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", file_path])
        elif system == "Windows":
            os.startfile(file_path)

    @log_time
    def action_open_file(self):
        """Open selected file with platform-specific default application."""
        # Only handle if we're on the files tab
        if (
            self.active_tab_id() != "tab-files"
            or not self.r_torrent
            or not self.file_list
        ):
            return

        table = self.query_one("#files")
        cursor_row = table.cursor_row

        # Check if cursor is at a valid position
        if (
            cursor_row is None
            or cursor_row < 0
            or cursor_row >= len(self.file_list)
        ):
            return

        selected_item = self.file_list[cursor_row]

        # Only open if it's a file (not a directory)
        if not selected_item["is_file"]:
            return

        # Get file ID and find corresponding file in torrent
        file_id = selected_item.get("id")
        if file_id is None:
            return

        # Find the file with this ID
        torrent_file = next(
            (f for f in self.r_torrent.files if f.id == file_id), None
        )
        if not torrent_file:
            return

        # Construct full file path
        location = self.r_torrent.download_dir
        file_path = os.path.join(location, torrent_file.name)

        # Check if file exists and open it
        if os.path.exists(file_path):
            try:
                self._open_file_with_system_app(file_path)
            except Exception:
                # Silently fail if opening doesn't work
                pass

    @log_time
    @on(TabbedContent.TabActivated)
    def handle_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.pane.id

        if tab_id == "tab-overview":
            self.query_one("#overview").focus()
        elif tab_id == "tab-files":
            self.query_one("#files").focus()
        elif tab_id == "tab-peers":
            self.query_one("#peers").focus()
        elif tab_id == "tab-trackers":
            self.query_one("#trackers").focus()

    def active_tab_id(self) -> str:
        return self.query_one(TabbedContent).active

    def open_default_tab(self) -> None:
        self.action_open_tab("tab-overview")

    @staticmethod
    @log_time
    def get_file_list(
        files: list[TorrentFile],
        priority_display: dict[TorrentFilePriority, str],
    ) -> list[dict[str, Any]]:
        """Convert file list to flattened tree with display formatting."""
        node = TorrentInfoPanel.create_file_tree(files)

        items_list: list[dict[str, Any]] = []

        def flatten_tree(
            node: dict[str, Any],
            prefix: str = "",
            is_last: bool = True,
            depth: int = 0,
            current_path: str = "",
        ) -> None:
            """Recursively flatten tree into list with tree symbols."""
            items = [(k, v) for k, v in node.items() if k != "__is_file__"]
            # Sort items by name (case-insensitive)
            items.sort(key=lambda x: x[0].lower())

            for i, (name, subtree) in enumerate(items):
                is_last_item = i == len(items) - 1

                # Choose the appropriate tree characters
                if prefix == "":
                    current_prefix = ""
                    symbol = ""  # No prefix for first level files
                else:
                    symbol = "├─ " if not is_last_item else "└─ "
                    current_prefix = prefix

                display_name = f"{current_prefix}{symbol}{name}"

                # Build the path for this item
                item_path = f"{current_path}{name}" if current_path else name

                if subtree.get("__is_file__", False):
                    f = subtree["file"]
                    completion = (f.completed / f.size) * 100
                    items_list.append(
                        {
                            "is_file": True,
                            "display_name": display_name,
                            "id": f.id,
                            "size": print_size(f.size),
                            "done": f"{completion:.0f}%",
                            "priority": priority_display[f.priority],
                            # Store raw priority for styling
                            "file_priority": f.priority,
                            "depth": depth,  # Track tree depth
                            "folder_path": None,  # Files don't have folder_path
                        }
                    )
                else:
                    items_list.append(
                        {
                            "is_file": False,
                            "display_name": display_name,
                            "id": None,
                            "size": None,
                            "done": None,
                            "priority": None,
                            "file_priority": None,
                            "depth": depth,  # Track tree depth
                            # Store folder path for child detection
                            "folder_path": item_path,
                        }
                    )

                    extension = "│  " if not is_last_item else "  "
                    new_prefix = current_prefix + extension
                    # Pass folder path with trailing slash for next level
                    next_path = f"{item_path}/"
                    flatten_tree(
                        subtree, new_prefix, is_last_item, depth + 1, next_path
                    )

        flatten_tree(node)

        return items_list

    @staticmethod
    @log_time
    def create_file_tree(files: list[TorrentFile]) -> dict[str, Any]:
        """Build hierarchical tree structure from flat list of files."""
        tree: dict[str, Any] = {}

        for file in files:
            parts = file.name.split("/")
            current = tree

            # Navigate/create the path in the tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {}

                # If this is the last part (filename), mark it as a file
                if i == len(parts) - 1:
                    current[part]["__is_file__"] = True
                    current[part]["file"] = file

                current = current[part]

        return tree
