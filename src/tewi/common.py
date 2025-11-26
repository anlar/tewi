from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NamedTuple
from enum import Enum, auto


@dataclass(frozen=True)
class TorrentDTO:
    """Data Transfer Object for torrent list view (immutable).

    Note: All size fields are in bytes, all speed fields are in bytes/second.
    """
    id: int | str
    name: str
    status: str
    total_size: int  # bytes
    size_when_done: int  # bytes
    left_until_done: int  # bytes
    percent_done: float
    eta: timedelta
    rate_upload: int  # bytes/second
    rate_download: int  # bytes/second
    ratio: float
    peers_connected: int
    peers_getting_from_us: int
    peers_sending_to_us: int
    uploaded_ever: int  # bytes
    priority: int | None
    added_date: datetime
    activity_date: datetime
    queue_position: int | None
    download_dir: str
    category: str | None = None
    labels: list[str] = field(default_factory=list)


class FilePriority(Enum):
    NOT_DOWNLOADING = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


@dataclass(frozen=True)
class FileDTO:
    """Data Transfer Object for torrent file information.

    Note: All size fields are in bytes.
    """
    id: int
    name: str
    size: int  # bytes
    completed: int  # bytes
    priority: FilePriority


class PeerState(Enum):
    INTERESTED = 'Interested'
    """Peer is interested in data and unchoked."""

    CHOKED = 'Choked'
    """Peer is interested in data BUT unchoked."""

    NONE = '-'
    """No active interest or transfer state."""


@dataclass(frozen=True)
class CategoryDTO:
    """Data Transfer Object for torrent categories (immutable)."""
    name: str
    save_path: str


class TorrentCategory(Enum):
    AUDIO = 'Audio'
    """Audio content (music, podcasts, audiobooks)."""

    VIDEO = 'Video'
    """Video content (movies, TV shows, videos)."""

    SOFTWARE = 'Software'
    """Software and applications."""

    GAMES = 'Games'
    """Games and gaming content."""

    XXX = 'XXX'
    """Adult content."""

    OTHER = 'Other'
    """Other content types."""

    UNKNOWN = '-'
    """Unknown or unspecified category."""


@dataclass(frozen=True)
class PeerDTO:
    """Data Transfer Object for peer information.

    Note: All speed fields are in bytes/second.
    """
    address: str
    client_name: str
    progress: float
    is_encrypted: bool
    rate_to_client: int  # bytes/second
    rate_to_peer: int  # bytes/second
    flag_str: str
    port: int
    connection_type: str
    direction: str
    country: str | None
    dl_state: PeerState
    ul_state: PeerState


@dataclass(frozen=True)
class TrackerDTO:
    """Data Transfer Object for tracker information."""
    host: str
    tier: int | None
    seeder_count: int | None
    leecher_count: int | None
    download_count: int | None
    status: str
    message: str
    peer_count: int | None
    last_announce: datetime | None = None
    next_announce: datetime | None = None
    last_scrape: datetime | None = None
    next_scrape: datetime | None = None


@dataclass(frozen=True)
class SearchResultDTO:
    """Data Transfer Object for web search results.

    Note: All size fields are in bytes.
    The fields dict contains provider-specific additional metadata.
    """
    title: str
    category: TorrentCategory
    seeders: int
    leechers: int
    size: int  # bytes
    files_count: int | None
    magnet_link: str
    info_hash: str
    upload_date: datetime | None  # Unix timestamp from API
    provider: str  # Display name of search provider
    page_url: str | None = None  # Link to torrent page on provider site
    fields: dict[str, str] | None = None  # Provider-specific metadata


@dataclass(frozen=True)
class TorrentDetailDTO:
    """Data Transfer Object for detailed torrent view (immutable).

    Note: All size fields are in bytes.
    """
    id: int | str
    name: str
    hash_string: str
    total_size: int  # bytes
    piece_count: int
    piece_size: int  # bytes
    is_private: bool
    comment: str
    creator: str
    labels: list[str]
    category: str | None
    status: str
    download_dir: str
    downloaded_ever: int  # bytes
    uploaded_ever: int  # bytes
    ratio: float
    error_string: str
    added_date: datetime
    start_date: datetime
    done_date: datetime
    activity_date: datetime
    peers_connected: int
    peers_sending_to_us: int
    peers_getting_from_us: int
    files: list[FileDTO]
    peers: list[PeerDTO]
    trackers: list[TrackerDTO]


class PageState(NamedTuple):
    current: int
    total: int


class SortOrder(NamedTuple):
    id: str
    name: str
    key_asc: str
    key_desc: str
    sort_func: None


sort_orders = [
        SortOrder('age', 'Age', 'a', 'A',
                  lambda t: t.added_date),
        SortOrder('name', 'Name', 'n', 'N',
                  lambda t: t.name.lower()),
        SortOrder('size', 'Size', 'z', 'Z',
                  lambda t: t.total_size),
        SortOrder('status', 'Status', 't', 'T',
                  lambda t: t.status),
        SortOrder('priority', 'Priority', 'i', 'I',
                  lambda t: t.priority),
        SortOrder('queue_order', 'Queue Order', 'o', 'O',
                  lambda t: t.queue_position),
        SortOrder('ratio', 'Ratio', 'r', 'R',
                  lambda t: t.ratio),
        SortOrder('progress', 'Progress', 'p', 'P',
                  lambda t: t.percent_done),
        SortOrder('activity', 'Activity', 'y', 'Y',
                  lambda t: t.activity_date),
        SortOrder('uploaded', 'Uploaded', 'u', 'U',
                  lambda t: t.uploaded_ever),
        SortOrder('peers', 'Peers', 'e', 'E',
                  lambda t: t.peers_connected),
        SortOrder('seeders', 'Seeders', 's', 'S',
                  lambda t: t.peers_sending_to_us),
        SortOrder('leechers', 'Leechers', 'l', 'L',
                  lambda t: t.peers_getting_from_us),
        ]


class FilterOption(NamedTuple):
    id: str
    name: str
    key: str
    display_name: str
    filter_func: None


filter_options = [
        FilterOption('all', 'All', 'a', '[u]A[/]ll',
                     lambda t: True),
        FilterOption('active', 'Active', 'c', 'A[u]c[/]tive',
                     lambda t: t.rate_download > 0 or t.rate_upload > 0),
        FilterOption('downloading', 'Downloading', 'd', '[u]D[/]ownloading',
                     lambda t: t.status == 'downloading'),
        FilterOption('seeding', 'Seeding', 's', '[u]S[/]eeding',
                     lambda t: t.status == 'seeding'),
        FilterOption('paused', 'Paused', 'p', '[u]P[/]aused',
                     lambda t: t.status == 'stopped'),
        FilterOption('finished', 'Finished', 'f', '[u]F[/]inished',
                     lambda t: t.percent_done >= 1.0),
        ]


def get_filter_by_id(filter_id: str) -> FilterOption:
    """Get filter option by ID.

    Args:
        filter_id: The filter ID to search for

    Returns:
        FilterOption matching the ID

    Raises:
        ValueError: If filter_id is not found
    """
    for filter_option in filter_options:
        if filter_option.id == filter_id:
            return filter_option
    raise ValueError(f"Unknown filter ID: {filter_id}")
