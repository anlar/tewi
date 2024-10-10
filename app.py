from transmission_rpc import Client
import textwrap

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, ScrollableContainer, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Header, Static, Label, ProgressBar

class TransmissionSession:
    def __init__(self, session, session_stats, torrents):
        self.session = session
        self.session_stats = session_stats
        self.torrents = torrents

class SessionUpdate(Message):
    def __init__(self, session):
        self.session = session
        super().__init__()

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
            yield Label('') # empty space between message and description
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

    def update_torrent(self, torrent) -> None:
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

        size_total = self.print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = self.print_size(self.t_size_total - self.t_size_left)
            result = f"{size_current} / {size_total} ({self.t_progress:.2f}%)"
        else:
            result = f"{size_total} (Ratio: {self.t_ratio:.2f})"

        result = result + f" | Status: {str(self.t_status)} | Seeders: {str(self.t_seeders)} | Leechers: {str(self.t_leechers)}"

        return result

    def compose(self) -> ComposeResult:
        with Grid(id="torrent-item-head"):
            yield Label(self.t_name, id = "torrent-item-head-name")
            yield Static("")
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(speed=TorrentItem.t_upload_speed)
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(speed=TorrentItem.t_download_speed)

        yield (ProgressBar(total = 1.0, show_percentage = False, show_eta = False)
               .data_bind(progress = TorrentItem.t_progress))

        yield ReactiveLabel(self.t_stats, id = "torrent-item-stats").data_bind(name=TorrentItem.t_stats)

    def print_size(self, num, suffix = "B", size_bytes = 1000):
        r_unit = None
        r_num = None

        for unit in ("", "k", "M", "G", "T", "P", "E", "Z"):
            if abs(num) < size_bytes:
                r_unit = unit
                r_num = num
                break
            num /= size_bytes

        if not r_unit:
            r_unit = 'Y'
            r_num = num

        round(r_num, 2)

        r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

        return f"{r_size} {r_unit}{suffix}"

class StatusLine(Widget):

    # recompose whole line to update speed block width
    alt_speed_enabled = reactive(False, recompose = True)
    alt_speed_up = reactive(0, recompose = True)
    alt_speed_down = reactive(0, recompose = True)

    def compose(self) -> ComposeResult:
        yield StatusLineSession()
        yield Static("")
        yield Static(self.get_alt_speed_label())
        yield Static(" ↑ ")
        yield SpeedIndicator(id = "upload")
        yield Static(" ↓ ")
        yield SpeedIndicator(id = "download")

    @on(SessionUpdate)
    def handle_session_update(self, message: SessionUpdate):
        session = message.session.session
        session_stats = message.session.session_stats

        self.update(
                session.version,
                session.alt_speed_enabled,
                session.alt_speed_up,
                session.alt_speed_down,
                session_stats.torrent_count,
                session_stats.upload_speed,
                session_stats.download_speed
                )

    def get_alt_speed_label(self):
        # alt speed always in KB
        if self.alt_speed_enabled:
            return f'[ Alt. Speed : ↑ {self.alt_speed_up} KB ↓ {self.alt_speed_down} KB ]'
        else:
            return ''

    def update(self, version,
               alt_speed_enabled, alt_speed_up, alt_speed_down,
               torrent_count,
               upload_speed, download_speed) -> None:

        session = self.query_one(StatusLineSession)
        session.version = version
        session.torrent_count = torrent_count

        upload = self.query_one("#upload")
        upload.speed = upload_speed

        download = self.query_one("#download")
        download.speed = download_speed

        self.alt_speed_enabled = alt_speed_enabled
        self.alt_speed_up = alt_speed_up
        self.alt_speed_down = alt_speed_down

class SpeedIndicator(Widget):

    speed = reactive(0)

    def render(self) -> str:
        return self.print_speed(self.speed)

    def print_speed(self, num, suffix = "B", speed_bytes = 1000) -> str:
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

class StatusLineSession(Widget):

    version = reactive('')
    torrent_count = reactive(0)

    def render(self) -> str:
        return f'Transmission {self.version} | Torrents: {self.torrent_count}'

class MainApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("k,up", "scroll_up", "UP", priority=True),
            Binding("j,down", "scroll_down", "DOWN", priority=True),
            Binding("p", "toggle_torrent", "Toggle torrent", priority=True),
            Binding("r", "remove_torrent", "Remove torrent", priority=True),
            Binding("R", "trash_torrent", "Trash torrent", priority=True),
            Binding("t", "toggle_alt_speed", "Toggle alt speed", priority=True),
            Binding("q", "quit", "Quit", priority=True),
            ]

    def __init__(self):
        super().__init__()

        self.tewi_version = 'DEV'

        self.c_host = 'localhost'
        self.c_port = '9091'

        self.client = Client(host = self.c_host, port = self.c_port)
        self.transmission_version = self.client.get_session().version

        self.selected_item = None

    def compose(self) -> ComposeResult:
        with Horizontal(id = "top-pane"):
            yield Static(f'Tewi {self.tewi_version}', classes = 'top-pane-column')
            yield Static('»»»', classes = 'top-pane-column top-pane-column-delimiter')
            yield Static(f'Transmission {self.transmission_version}', classes = 'top-pane-column')
            yield Static('»»»', classes = 'top-pane-column top-pane-column-delimiter')
            yield Static(f'{self.c_host}:{self.c_port}', classes = 'top-pane-column')
        yield ScrollableContainer(id = "torrents")
        yield StatusLine()

    def on_mount(self) -> None:
        self.load_session()
        self.set_interval(5, self.load_session)

    def action_toggle_torrent(self) -> None:
        if self.selected_item:
            status = self.selected_item.t_status

            if status == 'stopped':
                self.client.start_torrent(self.selected_item.t_id)
            else:
                self.client.stop_torrent(self.selected_item.t_id)

    def action_remove_torrent(self) -> None:
        self.remove_torrent(False)

    def action_trash_torrent(self) -> None:
        self.remove_torrent(True)

    def remove_torrent(self, delete_data: bool) -> None:
        if self.selected_item:

            def check_quit(confirmed: bool | None) -> None:
                if confirmed:
                    self.client.remove_torrent(self.selected_item.t_id,
                                          delete_data = delete_data)

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

            if delete_data:
                self.push_screen(
                        ConfirmationDialog(
                            message = "Remove torrent and delete data?",
                            description = "All data downloaded for this torrent will be deleted. Are you sure you want to remove it?"),
                        check_quit)
            else:
                self.push_screen(
                        ConfirmationDialog(
                            message = "Remove torrent?",
                            description = "Once removed, continuing the transfer will require the torrent file. Are you sure you want to remove it?"),
                        check_quit)

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

    def action_toggle_alt_speed(self) -> None:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled = not alt_speed_enabled)

    @on(SessionUpdate)
    def handle_session_update(self, message: SessionUpdate):
        session = message.session

        if self.is_equal_to_pane(session.torrents):
            items = self.query_one("#torrents").children

            for i, torrent in enumerate(session.torrents):
                items[i].update_torrent(torrent)
        else:
            self.create_pane(session)

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
                session = self.client.get_session(),
                session_stats = self.client.session_stats(),
                torrents = self.client.get_torrents()
        )

        session.torrents.sort(key = lambda t: t.name.lower())

        self.log(f'Load session from Transmission: {vars(session.session)}')
        self.log(f'Load session_stats from Transmission: {vars(session.session_stats)}')
        self.log(f'Load {len(session.torrents)} torrents from Transmission')

        status_line = self.query(StatusLine)

        if len(status_line) > 0:
            self.post_message(SessionUpdate(session))
            self.query_one(StatusLine).post_message(SessionUpdate(session))

if __name__ == "__main__":
    app = MainApp()
    app.run()
