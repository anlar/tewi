from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NamedTuple, Optional
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
    save_path: str | None


class Category:
    """Represents a Jackett category with ID, name, and hierarchy support."""

    def __init__(self, id: int, name: str, parent: Optional['Category'] = None):
        self.id = id
        self.name = name
        self.parent = parent

    @property
    def full_path(self) -> str:
        """Returns full hierarchical path like 'Console/XBox 360'."""
        if self.parent:
            return f"{self.parent.name}/{self.name}"
        return self.name

    @property
    def full_name(self) -> str:
        """Alias for full_path for backward compatibility."""
        return self.full_path

    @property
    def is_parent(self) -> bool:
        """Returns True if this is a parent category (ID ends in 000)."""
        return self.id % 1000 == 0

    def __repr__(self):
        return f"Category(id={self.id}, name='{self.name}')"


class JackettCategories:
    """Jackett category definitions with hierarchy."""

    # Parent categories
    CONSOLE = Category(1000, "Console")
    MOVIES = Category(2000, "Movies")
    AUDIO = Category(3000, "Audio")
    PC = Category(4000, "PC")
    TV = Category(5000, "TV")
    XXX = Category(6000, "XXX")
    BOOKS = Category(7000, "Books")
    OTHER = Category(8000, "Other")

    # Console subcategories
    CONSOLE_NDS = Category(1010, "NDS", CONSOLE)
    CONSOLE_PSP = Category(1020, "PSP", CONSOLE)
    CONSOLE_WII = Category(1030, "Wii", CONSOLE)
    CONSOLE_XBOX = Category(1040, "XBox", CONSOLE)
    CONSOLE_XBOX360 = Category(1050, "XBox 360", CONSOLE)
    CONSOLE_WIIWARE = Category(1060, "Wiiware", CONSOLE)
    CONSOLE_XBOX360DLC = Category(1070, "XBox 360 DLC", CONSOLE)
    CONSOLE_PS3 = Category(1080, "PS3", CONSOLE)
    CONSOLE_OTHER = Category(1090, "Other", CONSOLE)
    CONSOLE_3DS = Category(1110, "3DS", CONSOLE)
    CONSOLE_PSVITA = Category(1120, "PS Vita", CONSOLE)
    CONSOLE_WIIU = Category(1130, "WiiU", CONSOLE)
    CONSOLE_XBOXONE = Category(1140, "XBox One", CONSOLE)
    CONSOLE_PS4 = Category(1180, "PS4", CONSOLE)

    # Movies subcategories
    MOVIES_FOREIGN = Category(2010, "Foreign", MOVIES)
    MOVIES_OTHER = Category(2020, "Other", MOVIES)
    MOVIES_SD = Category(2030, "SD", MOVIES)
    MOVIES_HD = Category(2040, "HD", MOVIES)
    MOVIES_UHD = Category(2045, "UHD", MOVIES)
    MOVIES_BLURAY = Category(2050, "BluRay", MOVIES)
    MOVIES_3D = Category(2060, "3D", MOVIES)
    MOVIES_DVD = Category(2070, "DVD", MOVIES)
    MOVIES_WEBDL = Category(2080, "WEB-DL", MOVIES)

    # Audio subcategories
    AUDIO_MP3 = Category(3010, "MP3", AUDIO)
    AUDIO_VIDEO = Category(3020, "Video", AUDIO)
    AUDIO_AUDIOBOOK = Category(3030, "Audiobook", AUDIO)
    AUDIO_LOSSLESS = Category(3040, "Lossless", AUDIO)
    AUDIO_OTHER = Category(3050, "Other", AUDIO)
    AUDIO_FOREIGN = Category(3060, "Foreign", AUDIO)

    # PC subcategories
    PC_0DAY = Category(4010, "0day", PC)
    PC_ISO = Category(4020, "ISO", PC)
    PC_MAC = Category(4030, "Mac", PC)
    PC_MOBILE_OTHER = Category(4040, "Mobile-Other", PC)
    PC_GAMES = Category(4050, "Games", PC)
    PC_MOBILE_IOS = Category(4060, "Mobile-iOS", PC)
    PC_MOBILE_ANDROID = Category(4070, "Mobile-Android", PC)

    # TV subcategories
    TV_WEBDL = Category(5010, "WEB-DL", TV)
    TV_FOREIGN = Category(5020, "Foreign", TV)
    TV_SD = Category(5030, "SD", TV)
    TV_HD = Category(5040, "HD", TV)
    TV_UHD = Category(5045, "UHD", TV)
    TV_OTHER = Category(5050, "Other", TV)
    TV_SPORT = Category(5060, "Sport", TV)
    TV_ANIME = Category(5070, "Anime", TV)
    TV_DOCUMENTARY = Category(5080, "Documentary", TV)

    # XXX subcategories
    XXX_DVD = Category(6010, "DVD", XXX)
    XXX_WMV = Category(6020, "WMV", XXX)
    XXX_XVID = Category(6030, "XviD", XXX)
    XXX_X264 = Category(6040, "x264", XXX)
    XXX_UHD = Category(6045, "UHD", XXX)
    XXX_PACK = Category(6050, "Pack", XXX)
    XXX_IMAGESET = Category(6060, "ImageSet", XXX)
    XXX_OTHER = Category(6070, "Other", XXX)
    XXX_SD = Category(6080, "SD", XXX)
    XXX_WEBDL = Category(6090, "WEB-DL", XXX)

    # Books subcategories
    BOOKS_MAGS = Category(7010, "Mags", BOOKS)
    BOOKS_EBOOK = Category(7020, "EBook", BOOKS)
    BOOKS_COMICS = Category(7030, "Comics", BOOKS)
    BOOKS_TECHNICAL = Category(7040, "Technical", BOOKS)
    BOOKS_OTHER = Category(7050, "Other", BOOKS)
    BOOKS_FOREIGN = Category(7060, "Foreign", BOOKS)

    # Other subcategories
    OTHER_MISC = Category(8010, "Misc", OTHER)
    OTHER_HASHED = Category(8020, "Hashed", OTHER)

    @classmethod
    def get_by_id(cls, id: int) -> Optional[Category]:
        """Get category by ID."""
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Category) and attr.id == id:
                return attr
        return None

    @classmethod
    def all_categories(cls) -> list[Category]:
        """Get all categories."""
        categories = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Category):
                categories.append(attr)
        return sorted(categories, key=lambda c: c.id)

    @classmethod
    def parent_categories(cls) -> list[Category]:
        """Get only parent categories."""
        return [c for c in cls.all_categories() if c.is_parent]


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
    categories: list[Category]
    seeders: int
    leechers: int
    size: int  # bytes
    files_count: int | None
    magnet_link: str
    info_hash: str | None  # Optional: can be None for results without hash
    upload_date: datetime | None  # Unix timestamp from API
    provider: str  # Display name of search provider
    provider_id: str  # Unique provider identifier
    page_url: str | None = None  # Link to torrent page on provider site
    torrent_link: str | None = None  # HTTP/HTTPS torrent file URL
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


@dataclass(frozen=True)
class IndexerDTO:
    id: str
    name: str


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
                  lambda t: t.queue_position if t.queue_position is not None else float('inf')),
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
