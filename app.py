from transmission_rpc import Client

from textual import on
from textual.app import App, ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, ScrollableContainer
from textual.events import ScreenSuspend, ScreenResume
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Static, Label, Button, ProgressBar

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
            Binding("n", "close", "Cancel", priority=True),
            ]

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Confirmation"),
            Label(f'{self.message} Y/N'),
            id="dialog",
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_close(self) -> None:
        self.dismiss(False)

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

    next = None
    prev = None

    def __init__(self, torrent):
        super().__init__()
        self.update(torrent)

    def watch_selected(self, old_selected, new_selected):
        if new_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def update(self, torrent) -> None:
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
        size_total = self.print_size(self.t_size_total)

        size_label = None

        if self.t_size_left > 0:
            size_current = self.print_size(self.t_size_total - self.t_size_left)
            size_label = size_current + " / " + size_total
        else:
            size_label = size_total

        return f'{size_label} | Status: {str(self.t_status)} | Ratio: {self.t_ratio} | Priority: {self.t_priority} | Seeders: {str(self.t_seeders)} | Leechers: {str(self.t_leechers)} | ETA: {self.t_eta}'

    def compose(self) -> ComposeResult:
        with Grid(id="torrent-item-name"):
            yield Label(self.t_name)
            yield Static("")
            yield Static(" ↑ ")
            yield StatusLineSpeed().data_bind(speed=TorrentItem.t_upload_speed)
            yield Static(" ↓ ")
            yield StatusLineSpeed().data_bind(speed=TorrentItem.t_download_speed)

        yield ReactiveLabel(self.t_stats).data_bind(name=TorrentItem.t_stats)

        yield (ProgressBar(total = 1.0, show_eta = False)
               .data_bind(progress = TorrentItem.t_progress))

    def print_size(self, num, suffix="B"):
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"

class StatusLine(Widget):

    def compose(self) -> ComposeResult:
        yield StatusLineSession()
        yield Static("")
        yield Static(" ↑ ")
        yield StatusLineSpeed(id = "upload")
        yield Static(" ↓ ")
        yield StatusLineSpeed(id = "download")

    @on(SessionUpdate)
    def handle_session_update(self, message: SessionUpdate):
        session = message.session.session
        session_stats = message.session.session_stats

        self.update(
                session.version,
                session_stats.torrent_count,
                session_stats.upload_speed,
                session_stats.download_speed
                )

    def update(self, version, torrent_count,
               upload_speed, download_speed) -> None:

        session = self.query_one(StatusLineSession)
        session.version = version
        session.torrent_count = torrent_count

        upload = self.query_one("#upload")
        upload.speed = upload_speed

        download = self.query_one("#download")
        download.speed = download_speed

class StatusLineSpeed(Widget):

    speed = reactive(0)

    def render(self) -> str:
        return self.print_speed(self.speed)

    def print_speed(self, num, suffix="B"):
        # TODO: merge size formatter methods
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"

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
            Binding("t", "trash_torrent", "Trash torrent", priority=True),
            ]

    def __init__(self):
        super().__init__()

        self.client = Client()

        self.selected_item = None

    def compose(self) -> ComposeResult:
        yield Header()
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

                    prev = self.selected_item.prev
                    next = self.selected_item.next

                    self.selected_item.remove()
                    self.selected_item = None

                    if next:
                        next.prev = prev

                    if prev:
                        prev.next = next

                    new_selected = None
                    if next:
                        new_selected = next
                    elif prev:
                        new_selected = prev

                    if new_selected:
                        new_selected.selected = True
                        self.selected_item = new_selected
                        self.query_one("#torrents").scroll_to_widget(self.selected_item)

            if delete_data:
                self.push_screen(
                        ConfirmationDialog("Remove torrent from list and delete data?"),
                        check_quit)
            else:
                self.push_screen(
                        ConfirmationDialog("Remove torrent from list?"),
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
                if self.selected_item.prev:
                    self.selected_item.selected = False
                    self.selected_item = self.selected_item.prev
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
                if self.selected_item.next:
                    self.selected_item.selected = False
                    self.selected_item = self.selected_item.next
                    self.selected_item.selected = True
                    self.query_one("#torrents").scroll_to_widget(self.selected_item)

    @on(SessionUpdate)
    def handle_session_update(self, message: SessionUpdate):
        session = message.session

        if self.is_equal_to_pane(session.torrents):
            items = self.query_one("#torrents").children

            for i, torrent in enumerate(session.torrents):
                items[i].update(torrent)
        else:
            self.create_pane(session)

    def create_pane(self, session) -> None:
        torrents_pane = self.query_one("#torrents")
        torrents_pane.remove_children()

        self.selected_item = None

        prev = None
        for t in session.torrents:
            item = TorrentItem(t)
            torrents_pane.mount(item)

            if prev:
                prev.next = item
                item.prev = prev
                prev = item
            else:
                prev = item

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

