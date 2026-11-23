from dataclasses import dataclass

from textual.message import Message

from ..search.models import Category, SearchResult
from ..torrent.models import Torrent, TorrentFilePriority
from .models import FilterOption, MarkState, PageState, SortKey, TagType

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
class OpenFilterNameCommand(Message):
    pass


@dataclass
class OpenFilterTagCommand(Message):
    tag_type: TagType


@dataclass
class ClearFiltersCommand(Message):
    pass


@dataclass
class OpenUpdateTorrentLabelsCommand(Message):
    torrents: list[Torrent]


@dataclass
class OpenEditTorrentCommand(Message):
    torrents: list[Torrent]


@dataclass
class OpenUpdateTorrentCategoryCommand(Message):
    torrents: list[Torrent]


@dataclass
class EditTorrentCommand(Message):
    """Edit torrents: name is None to keep names (moving several)."""

    torrents: list[Torrent]
    name: str | None
    location: str


@dataclass
class UpdateTorrentCategoryCommand(Message):
    torrent_hashes: list[str]
    category: str | None


@dataclass
class RemoveTorrentCommand(Message):
    torrents: list[Torrent]


@dataclass
class TrashTorrentCommand(Message):
    torrents: list[Torrent]


@dataclass
class VerifyTorrentCommand(Message):
    torrent_hashes: list[str]


@dataclass
class ReannounceTorrentCommand(Message):
    torrent_hashes: list[str]


@dataclass
class ToggleTorrentCommand(Message):
    torrents: list[Torrent]


@dataclass
class StartAllTorrentsCommand(Message):
    pass


@dataclass
class StopAllTorrentsCommand(Message):
    pass


@dataclass
class ChangeTorrentPriorityCommand(Message):
    torrent_hashes: list[str]
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
    selected_preset: str | None = None


# Events


@dataclass
class TorrentRemovedEvent(Message):
    torrent_hashes: list[str]


@dataclass
class TorrentTrashedEvent(Message):
    torrent_hashes: list[str]


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
    sort_keys: tuple[SortKey, ...]
    notify: bool = True


@dataclass
class FilterUpdatedEvent(Message):
    filter_option: FilterOption


@dataclass
class FilterNameUpdatedEvent(Message):
    name: str


@dataclass
class FilterTagUpdatedEvent(Message):
    """Filter by category or label: name is None to clear it."""

    tag_type: TagType
    name: str | None


@dataclass
class PageChangedEvent(Message):
    state: PageState


@dataclass
class MarksChangedEvent(Message):
    state: MarkState


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
    # Shown literally below description (e.g. torrent names)
    items: list[str] | None = None
