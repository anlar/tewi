from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NamedTuple


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
    labels: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FileDTO:
    """Data Transfer Object for torrent file information.

    Note: All size fields are in bytes.
    """
    id: int
    name: str
    size: int  # bytes
    completed: int  # bytes
    selected: bool
    priority: int


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


@dataclass(frozen=True)
class TrackerDTO:
    """Data Transfer Object for tracker information."""
    host: str
    tier: int
    seeder_count: int
    leecher_count: int
    download_count: int
    status: str
    message: str
    peer_count: int


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
