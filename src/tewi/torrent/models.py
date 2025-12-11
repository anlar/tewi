from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import TypedDict


@dataclass(frozen=True)
class Torrent:
    """Data Transfer Object for torrent list view (immutable).

    Note: All size fields are in bytes, all speed fields are in bytes/second.
    Note: id field is optional and only populated by Transmission client.
    """

    id: int | None
    hash: str
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
    category: str | None
    labels: list[str]


class TorrentFilePriority(Enum):
    NOT_DOWNLOADING = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


@dataclass(frozen=True)
class TorrentFile:
    """Data Transfer Object for torrent file information.

    Note: All size fields are in bytes.
    """

    id: int
    name: str
    size: int  # bytes
    completed: int  # bytes
    priority: TorrentFilePriority


class TorrentPeerState(Enum):
    INTERESTED = "Interested"
    """Peer is interested in data and unchoked."""

    CHOKED = "Choked"
    """Peer is interested in data BUT unchoked."""

    NONE = "-"
    """No active interest or transfer state."""


@dataclass(frozen=True)
class TorrentCategory:
    """Data Transfer Object for torrent categories (immutable)."""

    name: str
    save_path: str | None


@dataclass(frozen=True)
class TorrentPeer:
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
    dl_state: TorrentPeerState
    ul_state: TorrentPeerState


@dataclass(frozen=True)
class TorrentTracker:
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
class TorrentDetail(Torrent):
    """Data Transfer Object for detailed torrent view (immutable).

    Extends Torrent and adds detail-specific fields plus files, peers,
    and trackers lists.

    Note: All size fields are in bytes.
    """

    # Detail-specific fields
    hash_string: str
    piece_count: int
    piece_size: int  # bytes
    is_private: bool
    comment: str
    creator: str
    downloaded_ever: int  # bytes
    error_string: str | None
    start_date: datetime | None
    done_date: datetime | None

    # Collections
    files: list[TorrentFile] = field(default_factory=list)
    peers: list[TorrentPeer] = field(default_factory=list)
    trackers: list[TorrentTracker] = field(default_factory=list)


class ClientMeta(TypedDict):
    """Metadata about the torrent client daemon."""

    name: str
    version: str


class ClientStats(TypedDict):
    """Statistics about current and cumulative session data.

    Note: All fields are optional as some clients may not provide certain
    statistics. Fields that are None will be displayed as "N/A" in the UI.
    """

    current_uploaded_bytes: int | None
    current_downloaded_bytes: int | None
    current_ratio: float | None
    current_active_seconds: int | None
    current_waste: int | None
    current_connected_peers: int | None

    total_uploaded_bytes: int | None
    total_downloaded_bytes: int | None
    total_ratio: float | None
    total_active_seconds: int | None
    total_started_count: int | None

    cache_read_hits: float | None
    cache_total_buffers_size: int | None

    perf_write_cache_overload: int | None
    perf_read_cache_overload: int | None
    perf_queued_io_jobs: int | None
    perf_average_time_queue: int | None
    perf_total_queued_size: int | None


class ClientSession(TypedDict):
    """Session information including speeds, settings, and torrent counts.

    Note: All speed values are in bytes/second for consistency across clients.
    """

    download_dir: str
    download_dir_free_space: int
    upload_speed: int
    download_speed: int
    alt_speed_enabled: bool
    alt_speed_up: int  # bytes/second
    alt_speed_down: int  # bytes/second

    torrents_complete_size: int
    torrents_total_size: int

    torrents_count: int
    torrents_down: int
    torrents_seed: int
    torrents_check: int
    torrents_stop: int


class ClientError(Exception):
    """Base exception for all client errors."""

    pass
