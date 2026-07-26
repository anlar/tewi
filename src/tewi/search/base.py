"""Abstract base class for torrent search providers."""

from abc import ABC, abstractmethod
from typing import Any

from ..ui.util import print_size
from .models import Category, Indexer, SearchResult
from .util import urlopen as _urlopen
from .util import urlopen_post as _urlopen_post


class BaseSearchProvider(ABC):
    """Abstract base class for torrent search providers.

    Each provider implements search functionality for a specific
    public tracker or torrent search engine.
    """

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize provider with a request timeout.

        Args:
            timeout: Default timeout in seconds for HTTP requests made
                    via `urlopen`/`urlopen_post`. When None, the
                    underlying `urlopen`/`urlopen_post` default is used.
        """
        self.timeout = timeout

    def urlopen(self, url: str, timeout: int | None = None) -> Any:
        """Open URL with the provider's configured timeout.

        Args:
            url: URL to fetch
            timeout: Override timeout in seconds (defaults to
                    `self.timeout` when not given)

        Returns:
            HTTP response context manager
        """
        if timeout is not None:
            return _urlopen(url, timeout=timeout)
        if self.timeout is not None:
            return _urlopen(url, timeout=self.timeout)
        return _urlopen(url)

    def urlopen_post(
        self, url: str, data: bytes, timeout: int | None = None
    ) -> Any:
        """Open URL with a POST request using the provider's timeout.

        Args:
            url: URL to fetch
            data: POST data as bytes
            timeout: Override timeout in seconds (defaults to
                    `self.timeout` when not given)

        Returns:
            HTTP response context manager
        """
        if timeout is not None:
            return _urlopen_post(url, data=data, timeout=timeout)
        if self.timeout is not None:
            return _urlopen_post(url, data=data, timeout=self.timeout)
        return _urlopen_post(url, data=data)

    @property
    @abstractmethod
    def id(self) -> str:
        """Return unique provider identifier for internal use.

        Returns:
            Unique string identifier (e.g., 'yts', 'jackett', 'tpb')
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @property
    def short_name(self) -> str:
        """Return a short provider name for compact display.

        Defaults to name. Override in providers with long names.
        """
        return self.name

    @abstractmethod
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Provider-specific search implementation.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)
            indexers: List of indexer IDs to search
                     (optional, for meta-providers)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If search fails
        """
        pass

    @abstractmethod
    def details_extended(self, result: SearchResult) -> str:
        """Generate provider-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with provider-specific details
        """

    def indexers(self) -> list[Indexer]:
        """Return list of available indexers for this provider.

        For most providers, this returns a single indexer (the provider
        itself) which is basic implementation. For meta-providers like
        Jackett, this returns all configured indexers.

        Returns:
            List of (indexer_id, indexer_name) tuples
        """
        return [Indexer(self.id, self.name)]

    def details_common(self, result: SearchResult) -> str:
        """Generate common torrent details for left column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with common details
        """
        md = "## General\n"
        md += f"- **Provider:** {self.name}\n"

        # Display categories with full names
        if result.categories:
            category_names = ", ".join(
                cat.full_name for cat in result.categories
            )
            md += f"- **Category:** {category_names}\n"
        else:
            md += "- **Category:** Unknown\n"

        md += f"- **Info Hash:** `{result.info_hash}`\n"

        md += "## Statistics\n"
        md += f"- **Size:** {print_size(result.size)}\n"
        md += f"- **Seeders:** {result.seeders}\n"
        md += f"- **Leechers:** {result.leechers}\n"

        if result.downloads:
            md += f"- **Downloads:** {result.downloads}\n"

        if result.files_count is not None:
            md += f"- **Files:** {result.files_count}\n"

        if result.upload_date:
            date_str = result.upload_date.strftime("%Y-%m-%d %H:%M")
            md += f"- **Uploaded:** {date_str}\n"

        if result.freeleech:
            md += "- **Freeleech:** Yes\n"

        return md
