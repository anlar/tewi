from textual.message import Message
from .common import PageState


class AddTorrent(Message):

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class TorrentLabelsUpdated(Message):

    def __init__(self, torrent_ids, value: str) -> None:
        super().__init__()
        self.torrent_ids = torrent_ids
        self.value = value


class SearchTorrent(Message):

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class SortOrderSelected(Message):

    def __init__(self, order: str, is_asc: bool) -> None:
        super().__init__()
        self.order = order
        self.is_asc = is_asc


class Notification(Message):

    def __init__(self,
                 message: str,
                 severity: str = 'information'):

        super().__init__()
        self.message = message
        self.severity = severity


class Confirm(Message):
    def __init__(self, message, description, check_quit):
        super().__init__()
        self.message = message
        self.description = description
        self.check_quit = check_quit


class OpenAddTorrent(Message):
    pass


class OpenUpdateTorrentLabels(Message):
    def __init__(self, torrent, torrent_ids):
        super().__init__()
        self.torrent = torrent
        self.torrent_ids = torrent_ids


class OpenSortOrder(Message):
    pass


class OpenSearch(Message):
    pass


class OpenPreferences(Message):
    pass


class PageChanged(Message):
    def __init__(self, state: PageState) -> None:
        super().__init__()
        self.state = state
