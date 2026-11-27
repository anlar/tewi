# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Abstract base class for torrent search providers."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from http.client import HTTPResponse
from typing import Any, ClassVar, TypeVar

from ..util.format import print_size
from .models import (
    Category,
    DetailsSection,
    Indexer,
    SearchResult,
)
from .util import LruCache
from .util import urlopen as _urlopen
from .util import urlopen_post as _urlopen_post

T = TypeVar("T")

# Maximum number of details downloaded by provider, kept in memory
DETAILS_CACHE_SIZE = 100


class BaseSearchProvider(ABC):
    """Abstract base class for torrent search providers."""

    # Whether `details_extended` requests provider site, so it's run in
    # background instead of UI thread
    remote_details: ClassVar[bool] = False

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize provider with a request timeout.

        Args:
            timeout: Default timeout in seconds for HTTP requests made
                via `urlopen`/`urlopen_post`. When None, the underlying
                `urlopen`/`urlopen_post` default is used.
        """
        self.timeout: int | None = timeout
        self._details_cache: LruCache[str, Any] = LruCache(DETAILS_CACHE_SIZE)

    @property
    @abstractmethod
    def id(self) -> str:
        """Return unique provider identifier for internal use.

        Returns:
            Unique string identifier (e.g., 'yts', 'jackett', 'tpb')
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""

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
        """Search provider for torrents matching query.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)
            indexers: List of indexer IDs to search (optional, for
                meta-providers)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If search fails. Providers wrap network and parse
                errors into it, its message is shown to user prefixed
                with provider name.
        """

    @abstractmethod
    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate provider-specific details of search result.

        Args:
            result: Search result to format

        Returns:
            Sections with provider-specific details
        """

    def details_extended_offline(
        self, result: SearchResult
    ) -> list[DetailsSection] | None:
        """Generate provider-specific details without network requests.

        Providers with remote details override it to use details cached
        by `_cached_details`.

        Args:
            result: Search result to format

        Returns:
            Sections with provider-specific details, or None if they have
            to be loaded by `details_extended`
        """
        return None if self.remote_details else self.details_extended(result)

    def _cached_details(
        self, key: str, fetch: Callable[[], T | None]
    ) -> T | None:
        """Return cached details of key, or fetch and cache them.

        Failures (None) aren't cached, so they are fetched again next time.

        Args:
            key: Details ID unique within provider (e.g. torrent ID)
            fetch: Loads details, returns None on failure

        Returns:
            Details, or None if they could not be loaded
        """
        value = self._details_cache.get(key)
        if value is None:
            value = fetch()
            if value is not None:
                self._details_cache.put(key, value)
        return value

    def indexers(self) -> list[Indexer]:
        """Return list of available indexers for this provider.

        By default returns a single indexer, the provider itself.
        Meta-providers like Jackett return all configured indexers.

        Returns:
            Indexers available for search
        """
        return [Indexer(self.id, self.name)]

    def urlopen(
        self,
        url: str,
        timeout: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        """Open URL with the provider's configured timeout.

        Args:
            url: URL to fetch
            timeout: Override timeout in seconds (defaults to
                `self.timeout` when not given)
            headers: Extra request headers (e.g. API key)

        Returns:
            HTTP response context manager
        """
        return _urlopen(url, **self._request_kwargs(timeout, headers))

    def urlopen_post(
        self,
        url: str,
        data: bytes,
        timeout: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTTPResponse:
        """Open URL with a POST request using the provider's timeout.

        Args:
            url: URL to fetch
            data: POST data as bytes
            timeout: Override timeout in seconds (defaults to
                `self.timeout` when not given)
            headers: Extra request headers (e.g. API key)

        Returns:
            HTTP response context manager
        """
        return _urlopen_post(
            url, data=data, **self._request_kwargs(timeout, headers)
        )

    def _request_kwargs(
        self, timeout: int | None, headers: dict[str, str] | None
    ) -> dict[str, Any]:
        """Build optional arguments for `urlopen`/`urlopen_post` helpers.

        Args:
            timeout: Override timeout in seconds, or None to use
                `self.timeout`
            headers: Extra request headers

        Returns:
            Keyword arguments, omitting ones to leave at helpers' default
        """
        if timeout is None:
            timeout = self.timeout
        kwargs: dict[str, Any] = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        if headers:
            kwargs["headers"] = headers
        return kwargs


def details_common(result: SearchResult) -> list[DetailsSection]:
    """Generate common details of search result.

    All fields are always shown, with "-" for values provider doesn't
    report. Providers of every source of merged result are listed.

    Args:
        result: Search result to format

    Returns:
        Sections with common details
    """
    providers = ", ".join(
        f"{s.provider} ({s.provider_source})"
        if s.provider_source
        else s.provider
        for s in result.all_sources
    )
    category = ", ".join(cat.full_path for cat in result.categories)

    general = DetailsSection(
        "General",
        fields=(
            ("Provider", providers),
            ("Category", category or "-"),
            ("Info Hash", result.info_hash or "-"),
        ),
    )

    size = print_size(result.size) if result.size is not None else "-"
    uploaded = (
        result.upload_date.strftime("%Y-%m-%d %H:%M")
        if result.upload_date is not None
        else "-"
    )

    stats = (
        ("Size", size),
        ("Seeders", _format_count(result.seeders)),
        ("Leechers", _format_count(result.leechers)),
        ("Downloads", _format_count(result.downloads)),
        ("Files", _format_count(result.files_count)),
        ("Uploaded", uploaded),
        ("Freeleech", "Yes" if result.freeleech else "No"),
    )

    return [general, DetailsSection("Statistics", fields=stats)]


def _format_count(value: int | None) -> str:
    """Format count for details, "-" when unknown."""
    return str(value) if value is not None else "-"
