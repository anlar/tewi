"""Abstract base class for torrent client implementations."""

import math
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import TypedDict

from ..common import SortOrder, TorrentDTO


class ClientMeta(TypedDict):
    """Metadata about the torrent client daemon."""
    name: str
    version: str


class ClientStats(TypedDict):
    """Statistics about current and cumulative session data.

    Note: All fields are optional as some clients may not provide certain statistics.
    Fields that are None will be displayed as "N/A" in the UI.
    """
    current_uploaded_bytes: int | None
    current_downloaded_bytes: int | None
    current_ratio: float | None
    current_active_seconds: int | None

    total_uploaded_bytes: int | None
    total_downloaded_bytes: int | None
    total_ratio: float | None
    total_active_seconds: int | None
    total_started_count: int | None


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

    sort_order: SortOrder
    sort_order_asc: bool


class ClientError(Exception):
    """Base exception for all client errors."""
    pass


class BaseClient(ABC):
    """Abstract base class defining the interface for all torrent clients."""

    @abstractmethod
    def __init__(self, host: str, port: str, username: str = None, password: str = None):
        """Initialize the client connection.

        Args:
            host: The hostname or IP address of the daemon
            port: The port number as a string
            username: Optional authentication username
            password: Optional authentication password
        """
        pass

    @abstractmethod
    def meta(self) -> ClientMeta:
        """Get daemon name and version.

        Returns:
            ClientMeta with name and version fields
        """
        pass

    @abstractmethod
    def stats(self) -> ClientStats:
        """Get current and cumulative session statistics.

        Returns:
            ClientStats with upload/download bytes, ratios, and active seconds
        """
        pass

    @abstractmethod
    def session(self, torrents: list[TorrentDTO], sort_order: SortOrder, sort_order_asc: bool) -> ClientSession:
        """Get session information with computed torrent counts.

        Args:
            torrents: List of torrents to compute counts from
            sort_order: Current sort order
            sort_order_asc: Whether sort order is ascending

        Returns:
            ClientSession with speeds, settings, and torrent counts
        """
        pass

    @abstractmethod
    def preferences(self) -> dict[str, str]:
        """Get session preferences as key-value pairs.

        Returns:
            Dictionary of preference keys and values
        """
        pass

    @abstractmethod
    def torrents(self) -> list[TorrentDTO]:
        """Get list of all torrents.

        Returns:
            List of TorrentDTO objects
        """
        pass

    def torrents_test(self, target_count: int) -> list[TorrentDTO]:
        """Get test torrent list (for performance testing).

        Args:
            target_count: Target number of test torrents to generate (approximate)

        Returns:
            List of duplicated TorrentDTO objects (~target_count items)
        """
        torrents = self.torrents()

        if not torrents:
            return []

        # Calculate multiplier to achieve approximately target_count torrents
        multiplier = max(1, math.ceil(target_count / len(torrents)))

        result = []
        idx = 1

        for i in range(multiplier):
            for t in torrents:
                t_copy = replace(t, id=idx, name=t.name + "-" + str(idx))
                result.append(t_copy)
                idx = idx + 1

        return result

    @abstractmethod
    def torrent(self, id: int | str):
        """Get detailed information about a specific torrent.

        Args:
            id: The torrent ID

        Returns:
            TorrentDetailDTO with complete torrent information
        """
        pass

    @abstractmethod
    def add_torrent(self, value: str) -> None:
        """Add a torrent from magnet link or file path.

        Args:
            value: Magnet link or path to .torrent file
        """
        pass

    @abstractmethod
    def start_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Start one or more torrents.

        Args:
            torrent_ids: Single torrent ID or list of IDs
        """
        pass

    @abstractmethod
    def stop_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Stop one or more torrents.

        Args:
            torrent_ids: Single torrent ID or list of IDs
        """
        pass

    @abstractmethod
    def remove_torrent(self, torrent_ids: int | str | list[int | str], delete_data: bool = False) -> None:
        """Remove one or more torrents.

        Args:
            torrent_ids: Single torrent ID or list of IDs
            delete_data: Whether to delete downloaded data
        """
        pass

    @abstractmethod
    def verify_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Verify one or more torrents.

        Args:
            torrent_ids: Single torrent ID or list of IDs
        """
        pass

    @abstractmethod
    def reannounce_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Reannounce one or more torrents to their trackers.

        Args:
            torrent_ids: Single torrent ID or list of IDs
        """
        pass

    @abstractmethod
    def start_all_torrents(self) -> None:
        """Start all torrents."""
        pass

    @abstractmethod
    def stop_all_torrents(self) -> None:
        """Stop all torrents."""
        pass

    @abstractmethod
    def update_labels(self, torrent_ids: int | str | list[int | str], labels: list[str]) -> None:
        """Update labels/tags for one or more torrents.

        Args:
            torrent_ids: Single torrent ID or list of IDs
            labels: List of label strings
        """
        pass

    @abstractmethod
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits.

        Returns:
            True if alt speed is now enabled, False otherwise
        """
        pass

    @abstractmethod
    def has_separate_id(self) -> bool:
        """Return True if this client has a separate ID field distinct from hash.

        Returns:
            True if ID should be displayed separately from hash, False otherwise
        """
        pass
