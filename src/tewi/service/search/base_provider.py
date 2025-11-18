"""Abstract base class for torrent search providers."""

import urllib.parse
from abc import ABC, abstractmethod
from ...common import SearchResultDTO


class BaseSearchProvider(ABC):
    """Abstract base class for torrent search providers.

    Each provider implements search functionality for a specific
    public tracker or torrent search engine.
    """

    @abstractmethod
    def search(self, query: str) -> list[SearchResultDTO]:
        """Search for torrents matching the query.

        Args:
            query: Search term

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If search fails
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider internal name."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return the provider display name for UI."""
        pass

    def _build_magnet_link(self, info_hash: str, name: str,
                           trackers: list[str] = None) -> str:
        """Build a magnet link from info hash, name, and optional trackers.

        Args:
            info_hash: 40-character hex string torrent info hash
            name: Torrent name to encode in magnet link
            trackers: Optional list of tracker URLs to append

        Returns:
            Complete magnet link string
        """
        encoded_name = urllib.parse.quote(name)
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}"

        if trackers:
            for tracker in trackers:
                encoded_tracker = urllib.parse.quote(tracker, safe='/:')
                magnet += f"&tr={encoded_tracker}"

        return magnet
