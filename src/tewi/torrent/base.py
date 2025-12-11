"""Abstract base class for torrent client implementations."""

import math
from abc import ABC, abstractmethod
from dataclasses import replace

from .models import (
    ClientMeta,
    ClientSession,
    ClientStats,
    Torrent,
    TorrentCategory,
    TorrentFilePriority,
)


class BaseClient(ABC):
    """Abstract base class defining the interface for all torrent clients."""

    TRACKER_STATUS_UNKNOWN = "Unknown"

    # ========================================================================
    # Client Lifecycle & Metadata
    # ========================================================================

    @abstractmethod
    def __init__(
        self, host: str, port: str, username: str = None, password: str = None
    ):
        """Initialize the client connection.

        Args:
            host: The hostname or IP address of the daemon
            port: The port number as a string
            username: Optional authentication username
            password: Optional authentication password
        """
        pass

    @abstractmethod
    def capable(self, capability_code: str) -> bool:
        """Check if the client supports a specific capability.

        Available capabilities:
            - "category": Support for torrent categories
            - "label": Support for torrent labels/tags
            - "set_priority": Support for setting bandwidth priority
            - "toggle_alt_speed": Support for alternative speed limits
            - "torrent_id": Use of numeric IDs (vs hash strings)

        Args:
            capability_code: The capability to check

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
    def torrent(self, hash: str):
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

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    def _count_torrents_by_status(
        self, torrents: list[Torrent]
    ) -> dict[str, int]:
        """Count torrents by status and calculate sizes.

        This is a helper method used internally by session() implementations
        to compute torrent statistics.

        Args:
            torrents: List of torrents to count

        Returns:
            Dictionary with keys:
                - count: Total number of torrents
                - down: Number of downloading torrents
                - seed: Number of seeding torrents
                - check: Number of checking torrents
                - stop: Number of stopped torrents
                - complete_size: Total completed bytes
                - total_size: Total size when done in bytes
        """
        count = len(torrents)
        down = 0
        seed = 0
        check = 0
        complete_size = 0
        total_size = 0

        for t in torrents:
            total_size += t.size_when_done
            complete_size += t.size_when_done - t.left_until_done

            if t.status == "downloading":
                down += 1
            elif t.status == "seeding":
                seed += 1
            elif t.status == "checking":
                check += 1

        stop = count - down - seed - check

        return {
            "count": count,
            "down": down,
            "seed": seed,
            "check": check,
            "stop": stop,
            "complete_size": complete_size,
            "total_size": total_size,
        }
