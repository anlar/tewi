from textual.message import Message
from .common import PageState


# Commands

class OpenTorrentInfoCommand(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class OpenTorrentListCommand(Message):
    pass


class OpenAddTorrentCommand(Message):
    pass


class AddTorrentCommand(Message):

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class OpenSortOrderCommand(Message):
    pass


class OpenUpdateTorrentLabelsCommand(Message):

    def __init__(self, torrent):
        super().__init__()
        self.torrent = torrent


class RemoveTorrentCommand(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class TrashTorrentCommand(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class VerifyTorrentCommand(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class ReannounceTorrentCommand(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class ToggleTorrentCommand(Message):

    def __init__(self, torrent_id: int, torrent_status) -> None:
        super().__init__()
        self.torrent_id = torrent_id
        self.torrent_status = torrent_status


class StartAllTorrentsCommand(Message):
    pass


class StopAllTorrentsCommand(Message):
    pass


class OpenSearchCommand(Message):
    pass


# Events

class TorrentRemovedEvent(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class TorrentTrashedEvent(Message):

    def __init__(self, torrent_id: int) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class SearchCompletedEvent(Message):

    def __init__(self, search_term: str) -> None:
        super().__init__()
        self.search_term = search_term


class TorrentLabelsUpdatedEvent(Message):

    def __init__(self, torrent_ids, value: str) -> None:
        super().__init__()
        self.torrent_ids = torrent_ids
        self.value = value


class SortOrderUpdatedEvent(Message):

    def __init__(self, order: str, is_asc: bool) -> None:
        super().__init__()
        self.order = order
        self.is_asc = is_asc


class PageChangedEvent(Message):

    def __init__(self, state: PageState) -> None:
        super().__init__()
        self.state = state


# Common

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
