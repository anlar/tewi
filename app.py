from transmission_rpc import Client

from textual.app import App, ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header, Static, Label, RichLog

class TransmissionSession:
    def __init__(self, session_stats, torrents):
        self.session_stats = session_stats
        self.torrents = torrents

class TorrentItem(Static):
    """Torrent item in main list"""

    selected = reactive(False, recompose=True)

    t_id = reactive(None, recompose=True)
    t_name = reactive(None, recompose=True)
    t_status = reactive(None, recompose=True)
    t_size_total = reactive(None, recompose=True)
    t_size_left = reactive(None, recompose=True)

    def __init__(self, torrent):
        super().__init__()
        self.update(torrent)

    def update(self, torrent) -> None:
        self.t_id = torrent.id
        self.t_name = torrent.name
        self.t_status = torrent.status
        self.t_size_total = torrent.total_size
        self.t_size_left = torrent.left_until_done

    def compose(self) -> ComposeResult:
        if self.selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

        yield Label(self.t_name)

        size_total = self.print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = self.print_size(self.t_size_total - self.t_size_left)
            yield Label(size_current + " / " + size_total)
        else:
            yield Label(size_total)

        yield Label(str(self.t_status))

    def print_size(self, num, suffix="B"):
        for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f}Yi{suffix}"

class StatusLine(Widget):
    def compose(self) -> ComposeResult:
        yield Static("Status", classes="box")
        yield Static("", classes="box")
        yield Static(" ↑ ", classes="box")
        yield StatusLineSpeed()
        yield Static(" ↓ ", classes="box")
        yield StatusLineSpeed()

    def update(self, upload_speed, download_speed) -> None:
        # TODO: use widget id's
        upload = self.query(StatusLineSpeed).first()
        upload.speed = upload_speed

        download = self.query(StatusLineSpeed).last()
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

class MainApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
            Binding("up", "scroll_up", "UP", priority=True),
            Binding("down", "scroll_down", "DOWN", priority=True),
            ]

    def __init__(self):
        super().__init__()
        self.selected_id = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(id = "torrents")
        yield StatusLine()
        # yield RichLog()

    def action_scroll_up(self) -> None:
        self.lg("UP")

        items = self.query(TorrentItem)

        if items:
            if self.selected_id is None:
                item = items[-1]
                item.selected = True
                self.selected_id = item.t_id
                self.query_one("#torrents").scroll_to_widget(item)
            else:
                select_next = False

                for i, item in enumerate(reversed(items)):
                    if select_next:
                        item.selected = True
                        self.selected_id = item.t_id
                        self.query_one("#torrents").scroll_to_widget(item)
                        break
                    else:
                        if item.selected and i != len(items) - 1:
                            item.selected = False
                            self.selected_id = None
                            select_next = True

    def action_scroll_down(self) -> None:
        self.lg("DOWN")

        items = self.query(TorrentItem)

        if items:
            if self.selected_id is None:
                item = items[0]
                item.selected = True
                self.selected_id = item.t_id
            else:
                select_next = False

                for i, item in enumerate(items):
                    if select_next:
                        item.selected = True
                        self.selected_id = item.t_id
                        self.query_one("#torrents").scroll_to_widget(item)
                        break
                    else:
                        if item.selected and i != len(items) - 1:
                            item.selected = False
                            self.selected_id = None
                            select_next = True

    def on_mount(self) -> None:
        self.create_pane()
        self.set_interval(5, self.update_pane)

    def create_pane(self, session=None) -> None:
        if session is None:
            session = self.load_session()

        torrents_pane = self.query_one("#torrents")
        torrents_pane.remove_children()

        self.selected_id = None

        for t in session.torrents:
            item = TorrentItem(t)
            torrents_pane.mount(item)

        self.query_one("#torrents").scroll_home()

        self.update_status_line(session.session_stats)

    def update_pane(self) -> None:
        session = self.load_session()

        if self.is_equal_to_pane(session.torrents):
            items = self.query_one("#torrents").children

            for i, torrent in enumerate(session.torrents):
                items[i].update(torrent)

            self.update_status_line(session.session_stats)
        else:
            self.create_pane(session)

    def update_status_line(self, session_stats) -> None:
        status_line = self.query_one(StatusLine)

        status_line.update(
                session_stats.upload_speed,
                session_stats.download_speed
                )

    def is_equal_to_pane(self, torrents) -> bool:
        items = self.query_one("#torrents").children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i].t_id:
                return False

        return True

    def load_session(self):
        client = Client()

        stats = TransmissionSession(
                session_stats = client.session_stats(),
                torrents =  client.get_torrents()
        )

        return stats

    def lg(self, value) -> None:
        # self.query_one(RichLog).write(value)
        pass

if __name__ == "__main__":
    app = MainApp()
    app.run()
