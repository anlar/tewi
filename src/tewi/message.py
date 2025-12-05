from textual.message import Message
from .common import FilterOption, PageState, Category


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


class OpenFilterCommand(Message):
    pass


class OpenUpdateTorrentLabelsCommand(Message):

    def __init__(self, torrent):
        super().__init__()
        self.torrent = torrent


class OpenEditTorrentCommand(Message):

    def __init__(self, torrent):
        super().__init__()
        self.torrent = torrent


class OpenUpdateTorrentCategoryCommand(Message):

    def __init__(self, torrent):
        super().__init__()
        self.torrent = torrent


class EditTorrentCommand(Message):

    def __init__(self, torrent_id: int | str, name: str,
                 location: str) -> None:
        super().__init__()
        self.torrent_id = torrent_id
        self.name = name
        self.location = location


class UpdateTorrentCategoryCommand(Message):

    def __init__(self, torrent_id: int | str, category: str | None) -> None:
        super().__init__()
        self.torrent_id = torrent_id
        self.category = category


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


class ChangeTorrentPriorityCommand(Message):

    def __init__(self, torrent_id: int, current_priority: int | None) -> None:
        super().__init__()
        self.torrent_id = torrent_id
        self.current_priority = current_priority


class ToggleFileDownloadCommand(Message):

    def __init__(self, torrent_id: int | str, file_ids: list[int], priority) -> None:
        super().__init__()
        self.torrent_id = torrent_id
        self.file_ids = file_ids
        self.priority = priority


class OpenSearchCommand(Message):
    pass


class AddTorrentFromWebSearchCommand(Message):

    def __init__(self, magnet_link: str) -> None:
        super().__init__()
        self.magnet_link = magnet_link


class WebSearchQuerySubmitted(Message):

    def __init__(self, query: str,
                 selected_indexers: list[str] | None = None,
                 selected_categories: list[Category] | None = None) -> None:
        super().__init__()
        self.query = query
        self.selected_indexers = selected_indexers
        self.selected_categories = selected_categories


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


class TorrentEditedEvent(Message):

    def __init__(self, torrent_id: int | str) -> None:
        super().__init__()
        self.torrent_id = torrent_id


class TorrentCategoryUpdatedEvent(Message):

    def __init__(self, torrent_id: int | str, category: str | None) -> None:
        super().__init__()
        self.torrent_id = torrent_id
        self.category = category


class SortOrderUpdatedEvent(Message):

    def __init__(self, order: str, is_asc: bool) -> None:
        super().__init__()
        self.order = order
        self.is_asc = is_asc


class FilterUpdatedEvent(Message):

    def __init__(self, filter_option: FilterOption) -> None:
        super().__init__()
        self.filter_option = filter_option


class PageChangedEvent(Message):

    def __init__(self, state: PageState) -> None:
        super().__init__()
        self.state = state


class SearchStateChangedEvent(Message):

    def __init__(self, current: int = None, total: int = None) -> None:
        super().__init__()
        self.current = current
        self.total = total


class WebSearchCompletedEvent(Message):

    def __init__(self, results: list) -> None:
        super().__init__()
        self.results = results


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
