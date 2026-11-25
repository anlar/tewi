"""Abstract base class for torrent search providers."""

from abc import ABC, abstractmethod
from typing import Any

from ..ui.util import print_size
from .models import (
    Category,
    DetailsLink,
    DetailsSection,
    Indexer,
    SearchResult,
)
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

    def urlopen(
        self,
        url: str,
        timeout: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Open URL with the provider's configured timeout.

        Args:
            url: URL to fetch
            timeout: Override timeout in seconds (defaults to
                    `self.timeout` when not given)
            headers: Extra request headers (e.g. API key)

        Returns:
            HTTP response context manager
        """
        kwargs = {}
        if timeout is None:
            timeout = self.timeout
        if timeout is not None:
            kwargs["timeout"] = timeout
        if headers:
            kwargs["headers"] = headers
        return _urlopen(url, **kwargs)

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
    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate provider-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Sections with provider-specific details
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

    def details_common(self, result: SearchResult) -> list[DetailsSection]:
        """Generate common torrent details for left column.

        Args:
            result: Search result to format

        Returns:
            Sections with common details
        """
        if result.categories:
            category = ", ".join(cat.full_path for cat in result.categories)
        else:
            category = "Unknown"

        general = DetailsSection(
            "General",
            fields=(
                ("Provider", result.provider),
                ("Category", category),
                ("Info Hash", result.info_hash or "Unknown"),
            ),
        )

        stats: list[tuple[str, str | DetailsLink]] = []
        if result.size is not None:
            stats.append(("Size", print_size(result.size)))
        else:
            stats.append(("Size", "Unknown"))

        if result.seeders:
            stats.append(("Seeders", str(result.seeders)))

        if result.leechers:
            stats.append(("Leechers", str(result.leechers)))

        if result.downloads:
            stats.append(("Downloads", str(result.downloads)))

        if result.files_count is not None:
            stats.append(("Files", str(result.files_count)))

        if result.upload_date:
            date_str = result.upload_date.strftime("%Y-%m-%d %H:%M")
            stats.append(("Uploaded", date_str))

        if result.freeleech:
            stats.append(("Freeleech", "Yes"))

        return [general, DetailsSection("Statistics", fields=tuple(stats))]
