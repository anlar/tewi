from transmission_rpc import Client
import random

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header, Static, Label, RichLog

class TorrentItem(Static):
    """Torrent item in main list"""

    item_name = reactive(None, recompose=True)
    selected = reactive(False, recompose=True)

    def __init__(self, torrent):
        super().__init__()

        self.torrent = torrent

        self.item_name = self.torrent.name

    def compose(self) -> ComposeResult:
        if self.selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

        yield Label(self.item_name)

        size_total = self.print_size(self.torrent.total_size)

        if self.torrent.left_until_done > 0:
            size_current = self.print_size(self.torrent.total_size - self.torrent.left_until_done)
            yield Label(size_current + " / " + size_total)
        else:
            yield Label(size_total)

        yield Label(str(self.torrent.status))

    def print_size(self, num, suffix="B"):
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
        yield Footer()
        yield ScrollableContainer(id = "torrents")
        #yield RichLog()

    def action_scroll_up(self) -> None:
        self.lg("UP")

        items = self.query(TorrentItem)

        if items:
            if self.selected_id is None:
                item = items[-1]
                item.selected = True
                self.selected_id = item.torrent.id
                self.query_one("#torrents").scroll_to_widget(item)
            else:
                select_next = False

                for i, item in enumerate(reversed(items)):
                    if select_next:
                        item.selected = True
                        self.selected_id = item.torrent.id
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
                self.selected_id = item.torrent.id
            else:
                select_next = False

                for i, item in enumerate(items):
                    if select_next:
                        item.selected = True
                        self.selected_id = item.torrent.id
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

    def create_pane(self, torrents=None) -> None:
        if torrents is None:
            torrents = self.load_torrents()

        torrents_pane = self.query_one("#torrents")
        torrents_pane.remove_children()

        self.selected_id = None

        for t in torrents:
            item = TorrentItem(t)
            torrents_pane.mount(item)

    def update_pane(self) -> None:
        torrents = self.load_torrents()

        if self.is_equal_to_pane(torrents):
            items = self.query_one("#torrents").children

            # TODO: update item details
            for i, torrent in enumerate(torrents):
                items[i].item_name = items[i].item_name + "+"
        else:
            self.create_pane(torrents)

    def is_equal_to_pane(self, torrents) -> bool:
        items = self.query_one("#torrents").children

        if len(torrents) != len(items):
            return False

        for i, torrent in enumerate(torrents):
            if torrent.id != items[i].torrent.id:
                return False

        return True

    def load_torrents(self):
        client = Client()
        return client.get_torrents()

    def lg(self, value) -> None:
        #self.query_one(RichLog).write(value)
        pass

if __name__ == "__main__":
    app = MainApp()
    app.run()
