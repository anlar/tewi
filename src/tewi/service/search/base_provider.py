"""Abstract base class for torrent search providers."""

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
