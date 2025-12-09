from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
