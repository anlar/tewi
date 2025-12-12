"""Abstract base class for torrent client implementations."""

from abc import ABC, abstractmethod
from enum import Enum

from .models import (
    ClientMeta,
    ClientSession,
    ClientStats,
    Torrent,
    TorrentCategory,
    TorrentDetail,
    TorrentFilePriority,
)
from .util import torrents_test as util_torrents_test


class ClientCapability(str, Enum):
    """Client capability identifiers.

    These constants define features that may or may not be supported
    by different torrent client implementations.
    """

    CATEGORY = "category"
    """Support for torrent categories."""

    LABEL = "label"
    """Support for torrent labels/tags."""

    SET_PRIORITY = "set_priority"
    """Support for setting bandwidth priority."""

    TOGGLE_ALT_SPEED = "toggle_alt_speed"
    """Support for alternative speed limits."""

    TORRENT_ID = "torrent_id"
    """Use of numeric IDs (vs hash strings)."""


class BaseClient(ABC):
    """Abstract base class defining the interface for all torrent clients."""

    TRACKER_STATUS_UNKNOWN = "Unknown"

    # ========================================================================
    # Client Lifecycle & Metadata
    # ========================================================================

    @abstractmethod
    def __init__(
        self,
        host: str,
        port: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the client connection.

        Args:
            host: The hostname or IP address of the daemon
            port: The port number as a string
            username: Optional authentication username
            password: Optional authentication password
        """
        pass

    @abstractmethod
    def capable(self, capability: ClientCapability) -> bool:
        """Check if the client supports a specific capability.

        Available capabilities are defined in ClientCapability enum.

        Args:
            capability: The capability to check (ClientCapability enum value)

        Returns:
            True if the capability is supported, False otherwise
        """
        pass

    @abstractmethod
    def meta(self) -> ClientMeta:
        """Get daemon name and version.

        Returns:
            ClientMeta with name and version fields
        """
        pass

    # ========================================================================
    # Session & Global Settings
    # ========================================================================

    @abstractmethod
    def session(self, torrents: list[Torrent]) -> ClientSession:
        """Get session information with computed torrent counts.

        Args:
            torrents: List of torrents to compute counts from

        Returns:
            ClientSession with speeds, settings, and torrent counts
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
    def preferences(self) -> dict[str, str]:
        """Get session preferences as key-value pairs.

        Returns:
            Dictionary of preference keys and values
        """
        pass

    @abstractmethod
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits.

        Returns:
            True if alt speed is now enabled, False otherwise
        """
        pass

    # ========================================================================
    # Torrent Retrieval
    # ========================================================================

    @abstractmethod
    def torrents(self) -> list[Torrent]:
        """Get list of all torrents.

        Returns:
            List of Torrent objects
        """
        pass

    def torrents_test(self, target_count: int) -> list[Torrent]:
        """Get test torrent list (for performance testing).

        Args:
            target_count: Target number of test torrents to generate
                (approximate)

        Returns:
            List of duplicated Torrent objects (~target_count items)
        """
        torrents = self.torrents()
        return util_torrents_test(torrents, target_count)

    @abstractmethod
    def torrent(self, hash: str) -> TorrentDetail:
        """Get detailed information about a specific torrent.

        Args:
            hash: The torrent hash string

        Returns:
            TorrentDetail with complete torrent information
        """
        pass

    # ========================================================================
    # Torrent Lifecycle Operations
    # ========================================================================

    @abstractmethod
    def add_torrent(self, value: str) -> None:
        """Add a torrent from magnet link or file path.

        Args:
            value: Magnet link or path to .torrent file
        """
        pass

    @abstractmethod
    def start_torrent(self, hashes: str | list[str]) -> None:
        """Start one or more torrents.

        Args:
            hashes: Single torrent hash or list of hashes
        """
        pass

    @abstractmethod
    def start_all_torrents(self) -> None:
        """Start all torrents in the client."""
        pass

    @abstractmethod
    def stop_torrent(self, hashes: str | list[str]) -> None:
        """Stop one or more torrents.

        Args:
            hashes: Single torrent hash or list of hashes
        """
        pass

    @abstractmethod
    def stop_all_torrents(self) -> None:
        """Stop all torrents in the client."""
        pass

    @abstractmethod
    def remove_torrent(
        self,
        hashes: str | list[str],
        delete_data: bool = False,
    ) -> None:
        """Remove one or more torrents.

        Args:
            hashes: Single torrent hash or list of hashes
            delete_data: Whether to delete downloaded data
        """
        pass

    @abstractmethod
    def verify_torrent(self, hashes: str | list[str]) -> None:
        """Verify one or more torrents (rehash data).

        Args:
            hashes: Single torrent hash or list of hashes
        """
        pass

    @abstractmethod
    def reannounce_torrent(self, hashes: str | list[str]) -> None:
        """Reannounce one or more torrents to their trackers.

        Args:
            hashes: Single torrent hash or list of hashes
        """
        pass

    # ========================================================================
    # Torrent Organization & Metadata
    # ========================================================================

    @abstractmethod
    def edit_torrent(self, hash: str, name: str, location: str) -> None:
        """Edit torrent name and download location.

        Args:
            hash: The torrent hash string
            name: New torrent name
            location: New download location path
        """
        pass

    @abstractmethod
    def get_categories(self) -> list[TorrentCategory]:
        """Get list of available torrent categories.

        Returns:
            List of TorrentCategory objects with name and save_path
        """
        pass

    @abstractmethod
    def set_category(
        self, hashes: str | list[str], category: str | None
    ) -> None:
        """Set category for one or more torrents.

        Args:
            hashes: Single torrent hash or list of hashes
            category: Category name or None to clear category
        """
        pass

    @abstractmethod
    def update_labels(self, hashes: str | list[str], labels: list[str]) -> None:
        """Update labels/tags for one or more torrents.

        Args:
            hashes: Single torrent hash or list of hashes
            labels: List of label strings to apply
        """
        pass

    # ========================================================================
    # Priority Management
    # ========================================================================

    @abstractmethod
    def set_priority(self, hashes: str | list[str], priority: int) -> None:
        """Set bandwidth priority for one or more torrents.

        Args:
            hashes: Single torrent hash or list of hashes
            priority: Priority level (-1=low, 0=normal, 1=high)
        """
        pass

    @abstractmethod
    def set_file_priority(
        self,
        hash: str,
        file_ids: list[int],
        priority: TorrentFilePriority,
    ) -> None:
        """Set download priority for files within a torrent.

        Args:
            hash: The torrent hash string
            file_ids: List of file IDs to update
            priority: TorrentFilePriority enum value
        """
        pass
