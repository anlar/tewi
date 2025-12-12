from dataclasses import dataclass

from textual.message import Message

from ..search.models import Category, SearchResult
from ..torrent.models import Torrent, TorrentFilePriority
from .models import FilterOption, PageState

# Commands


@dataclass
class OpenTorrentInfoCommand(Message):
    torrent_hash: str


@dataclass
class OpenTorrentListCommand(Message):
    pass


@dataclass
class OpenAddTorrentCommand(Message):
    pass


@dataclass
class AddTorrentCommand(Message):
    value: str


@dataclass
class OpenSortOrderCommand(Message):
    pass


@dataclass
class OpenFilterCommand(Message):
    pass


@dataclass
class OpenUpdateTorrentLabelsCommand(Message):
    torrent: Torrent


@dataclass
class OpenEditTorrentCommand(Message):
    torrent: Torrent


@dataclass
class OpenUpdateTorrentCategoryCommand(Message):
    torrent: Torrent


@dataclass
class EditTorrentCommand(Message):
    torrent_hash: str
    name: str
    location: str


@dataclass
class UpdateTorrentCategoryCommand(Message):
    torrent_hash: str
    category: str | None


@dataclass
class RemoveTorrentCommand(Message):
    torrent_hash: str


@dataclass
class TrashTorrentCommand(Message):
    torrent_hash: str


@dataclass
class VerifyTorrentCommand(Message):
    torrent_hash: str


@dataclass
class ReannounceTorrentCommand(Message):
    torrent_hash: str


@dataclass
class ToggleTorrentCommand(Message):
    torrent_hash: str
    torrent_status: str


@dataclass
class StartAllTorrentsCommand(Message):
    pass


@dataclass
class StopAllTorrentsCommand(Message):
    pass


@dataclass
class ChangeTorrentPriorityCommand(Message):
    torrent_hash: str
    current_priority: int | None


@dataclass
class ToggleFileDownloadCommand(Message):
    torrent_hash: str
    file_ids: list[int]
    priority: TorrentFilePriority


@dataclass
class OpenSearchCommand(Message):
    pass


@dataclass
class AddTorrentFromWebSearchCommand(Message):
    magnet_link: str


@dataclass
class WebSearchQuerySubmitted(Message):
    query: str
    selected_indexers: list[str] | None = None
    selected_categories: list[Category] | None = None


# Events


@dataclass
class TorrentRemovedEvent(Message):
    torrent_hash: str


@dataclass
class TorrentTrashedEvent(Message):
    torrent_hash: str


@dataclass
class SearchCompletedEvent(Message):
    search_term: str


@dataclass
class TorrentLabelsUpdatedEvent(Message):
    torrent_hashes: list[str]
    value: str


@dataclass
class TorrentEditedEvent(Message):
    torrent_hash: str


@dataclass
class TorrentCategoryUpdatedEvent(Message):
    torrent_hash: str
    category: str | None


@dataclass
class SortOrderUpdatedEvent(Message):
    order: str
    is_asc: bool


@dataclass
class FilterUpdatedEvent(Message):
    filter_option: FilterOption


@dataclass
class PageChangedEvent(Message):
    state: PageState


@dataclass
class SearchStateChangedEvent(Message):
    current: int | None = None
    total: int | None = None


@dataclass
class WebSearchCompletedEvent(Message):
    results: list[SearchResult]


# Common


@dataclass
class Notification(Message):
    message: str
    severity: str = "information"


@dataclass
class Confirm(Message):
    message: str
    description: str
    check_quit: bool
