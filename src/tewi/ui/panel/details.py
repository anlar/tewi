from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Horizontal, Container, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, DataTable, TabbedContent, TabPane

from ..widget.common import ReactiveLabel
from ...util.print import print_size, print_speed, print_time_ago
from ...util.decorator import log_time
from ...util.geoip import get_country


class TorrentInfoPanel(ScrollableContainer):

    class TorrentViewClosed(Message):
        pass

    BINDINGS = [
            Binding("enter", "view_list", "[Navigation] View torrent list"),
            Binding("h", "go_left", "[Navigation] Go left"),
            Binding("l", "go_right", "[Navigation] Go right"),

            Binding("k,up", "scroll_up", "[Navigation] Scroll up"),
            Binding("j,down", "scroll_down", "[Navigation] Scroll down"),

            Binding("g", "scroll_top", "[Navigation] Scroll to the top"),
            Binding("G", "scroll_bottom", "[Navigation] Scroll to the bottom"),
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
                    with Vertical():
                        with Container(classes="overview-block") as block:
                            block.border_title = 'Details'

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
                            yield Static("Location:", classes="name")
                            yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_location)
                            yield Static("Error:", classes="name")
                            yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_error)

                        with Horizontal(classes="overview-bottom"):
                            # Should be the largest block in the bottom row for all other
                            # blocks to use height=100% to maximize their heights,
                            # that is why it is missing 'overview-small-block' CSS class
                            # State panel - 25% width
                            with Container(classes="overview-block state-panel") as block:
                                block.border_title = 'State'

                                yield Static("Status:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_status)
                                yield Static("Downloaded:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_downloaded)
                                yield Static("Uploaded:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_uploaded)
                                yield Static("Ratio:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_ratio)

                            with Container(classes="overview-block overview-small-block dates-panel") as block:
                                block.border_title = 'Dates'

                                yield Static("Added:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_added)
                                yield Static("Started:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_started)
                                yield Static("Completed:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_completed)
                                yield Static("Last active:", classes="name")
                                yield ReactiveLabel().data_bind(name=TorrentInfoPanel.t_date_active)

                            with Container(classes="overview-block overview-small-block peers-panel") as block:
                                block.border_title = 'Peers'

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
            self.t_size = print_size(torrent.total_size)
            self.t_files = str(len(torrent.get_files()))
            self.t_pieces = f"{torrent.piece_count} @ {print_size(torrent.piece_size, size_bytes=1024)}"

            if torrent.is_private:
                self.t_privacy = "Private to this tracker -- DHT and PEX disabled"
            else:
                self.t_privacy = "Public torrent"

            self.t_comment = torrent.comment if torrent.comment else "None"
            self.t_creator = torrent.creator if torrent.creator else "None"
            self.t_labels = ", ".join(torrent.labels) if len(torrent.labels) > 0 else "None"

            self.t_status = torrent.status.title()
            self.t_location = torrent.download_dir
            self.t_downloaded = print_size(torrent.downloaded_ever)
            self.t_uploaded = print_size(torrent.uploaded_ever)
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

            file_tree = self.create_file_tree(self.r_torrent.get_files())
            self.draw_file_table(table, file_tree)

            table = self.query_one("#peers")
            table.clear()

            for p in self.r_torrent.peers:
                progress = p["progress"] * 100
                table.add_row("Yes" if p["isEncrypted"] else "No",
                              print_speed(p["rateToClient"], True),
                              print_speed(p["rateToPeer"], True),
                              f'{progress:.0f}%',
                              p["flagStr"],
                              get_country(p["address"]),
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

    def create_file_tree(self, torrents) -> dict:
        # Build the tree structure
        tree = {}

        for torrent in torrents:
            parts = torrent.name.split('/')
            current = tree

            # Navigate/create the path in the tree
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {}

                # If this is the last part (filename), mark it as a file
                if i == len(parts) - 1:
                    current[part]['__is_file__'] = True
                    current[part]['torrent'] = torrent

                current = current[part]

        return tree

    def draw_file_table(self, table, node, prefix="", is_last=True) -> None:
        items = [(k, v) for k, v in node.items() if k != '__is_file__']

        for i, (name, subtree) in enumerate(items):
            is_last_item = i == len(items) - 1

            # Choose the appropriate tree characters
            if prefix == "":
                current_prefix = ""
                symbol = ""  # No prefix for first level files
            else:
                symbol = "├─ " if not is_last_item else "└─ "
                current_prefix = prefix

            if subtree.get('__is_file__', False):
                f = subtree['torrent']

                completion = (f.completed / f.size) * 100
                table.add_row(f.id,
                              print_size(f.size),
                              f'{completion:.0f}%',
                              'Yes' if f.selected else 'No',
                              self.print_priority(f.priority),
                              f"{current_prefix}{symbol}{name}")
            else:
                table.add_row(None,
                              None,
                              None,
                              None,
                              None,
                              f"{current_prefix}{symbol}{name}")

                # print directory content
                extension = "│  " if not is_last_item else "  "
                new_prefix = current_prefix + extension
                self.draw_file_table(table, subtree, new_prefix, is_last_item)

    def print_count(self, value: int) -> str:
        if value == -1:
            return "N/A"

        return value

    def print_datetime(self, value: datetime) -> str:
        if value:
            time_ago = print_time_ago(value)
            return f"{value.strftime('%Y-%m-%d %H:%M:%S')} ({time_ago})"
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
