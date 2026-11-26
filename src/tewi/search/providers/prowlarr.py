# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Prowlarr torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import (
    Category,
    DetailsLink,
    DetailsSection,
    Indexer,
    SearchResult,
    StandardCategories,
)
from ..util import (
    MAX_ERROR_BODY_SIZE,
    build_magnet_link,
    details_value,
    imdb_link,
    local_time,
    parse_iso_date,
    read_response,
)

logger = get_logger()


class ProwlarrProvider(BaseSearchProvider):
    """Search provider for Prowlarr (meta-indexer).

    Prowlarr provides unified access to multiple torrent indexers
    through a single API. Requires local Prowlarr instance.
    Documentation: https://github.com/Prowlarr/Prowlarr
    """

    def __init__(
        self,
        prowlarr_url: str | None = None,
        api_key: str | None = None,
        multi_indexer: bool = False,
        timeout: int | None = None,
    ):
        """Initialize Prowlarr provider with configuration.

        Args:
            prowlarr_url: Base URL of Prowlarr instance
            api_key: API key for Prowlarr authentication
            multi_indexer: If True, load all indexers individually.
                          If False, use single "all" endpoint (default)
            timeout: Default timeout in seconds for search requests
        """
        super().__init__(timeout)
        self.prowlarr_url: str | None = prowlarr_url
        self.api_key: str | None = api_key
        self.multi_indexer: bool = multi_indexer

        self._config_error: str | None = self._validate_config(
            prowlarr_url, api_key
        )

        self._cached_indexers: list[Indexer] | None = None
        self._cache_time: datetime | None = None
        self._cache_duration: timedelta = timedelta(minutes=10)

    @property
    def id(self) -> str:
        return "prowlarr"

    @property
    def name(self) -> str:
        return "Prowlarr"

    def indexers(self) -> list[Indexer]:
        """Return list of configured indexers from Prowlarr instance.

        When multi_indexer is False, returns a single "Prowlarr" indexer
        that searches all indexers.

        When multi_indexer is True, fetches and returns all individual
        indexers. Uses a 10-minute cache to avoid repeated API calls.

        Returns:
            List of Indexer objects from Prowlarr,
            or empty list if not configured or error occurs
        """
        if self._config_error:
            logger.debug(f"Prowlarr not configured: {self._config_error}")
            return []

        # If multi_indexer is disabled, return single "Prowlarr" indexer
        if not self.multi_indexer:
            logger.debug("Prowlarr: multi_indexer disabled, returning single")
            return [Indexer(id="prowlarr:all", name="Prowlarr")]

        # Check if cache is valid
        if self._is_cache_valid():
            logger.debug("Prowlarr: returning cached indexers")
            return self._cached_indexers

        try:
            url = self._build_indexers_url()
            data = self._fetch_indexers(url)
            indexers = self._process_indexers(data)
            logger.info(f"Prowlarr: loaded {len(indexers)} indexers")

            # Update cache
            self._cached_indexers = indexers
            self._cache_time = datetime.now()

            return indexers
        except Exception as e:
            # Return empty list if indexers cannot be fetched
            logger.warning(f"Failed to load Prowlarr indexers: {e}")
            return []

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search Prowlarr for torrents across indexers.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)
            indexers: Indexer IDs to search (optional - if None, search all)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails or not configured
        """
        if self._config_error:
            raise Exception(self._config_error)

        if not query or not query.strip():
            return []

        # Without multi_indexer, single "all" indexer is selected
        if not self.multi_indexer or (indexers and "all" in indexers):
            indexers = None

        # Build URL with optional indexer and category filtering
        url = self._build_search_url(query, categories, indexers)
        data = self._fetch_results(url)
        return self._process_results(data)

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate Prowlarr-specific details for right column.

        Prints all provider-specific fields from the search result.

        Args:
            result: Search result to format

        Returns:
            Sections with Prowlarr details
        """
        if not result.extra:
            return []

        # All fields in sorted order for consistent display
        fields: list[tuple[str, str | DetailsLink]] = []
        for key in sorted(result.extra.keys()):
            field = self._transform_field(key, result.extra[key])
            if field:
                fields.append(field)

        # Most fields are often empty (e.g. IDs are 0)
        if not fields:
            return []
        return [DetailsSection("Indexer Info", fields=tuple(fields))]

    def _validate_config(
        self, prowlarr_url: str | None, api_key: str | None
    ) -> str | None:
        """Validate configuration and return error message if invalid.

        Args:
            prowlarr_url: Base URL of Prowlarr instance
            api_key: API key for Prowlarr authentication

        Returns:
            Error message string if invalid, None if valid
        """
        if not prowlarr_url or not prowlarr_url.strip():
            return (
                "Prowlarr URL not configured. "
                "Set prowlarr_url in [search] section."
            )
        if not api_key or not api_key.strip():
            return (
                "Prowlarr API key not configured. "
                "Set prowlarr_api_key in [search] section."
            )
        return None

    def _is_cache_valid(self) -> bool:
        """Check if cached indexers are still valid.

        Returns:
            True if cache exists and hasn't expired, False otherwise
        """
        if self._cached_indexers is None or self._cache_time is None:
            return False

        time_elapsed = datetime.now() - self._cache_time
        return time_elapsed < self._cache_duration

    def _build_indexers_url(self) -> str:
        """Build Prowlarr API indexers URL.

        Returns:
            Complete URL to fetch indexers list
        """
        base_url = self.prowlarr_url.rstrip("/")
        return f"{base_url}/api/v1/indexer"

    def _auth_headers(self) -> dict[str, str]:
        """Get API key header.

        Key is sent in header instead of URL query, so it doesn't get to
        access logs of Prowlarr and proxies in front of it.
        """
        return {"X-Api-Key": self.api_key}

    def _fetch_indexers(self, url: str) -> Any:
        """Fetch and parse JSON indexers list from Prowlarr API.

        Args:
            url: Complete API URL

        Returns:
            Parsed JSON data as list

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            with self.urlopen(
                url, timeout=10, headers=self._auth_headers()
            ) as response:
                return json.loads(read_response(response).decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Exception("Invalid Prowlarr API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Prowlarr at {self.prowlarr_url}: {e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Prowlarr JSON response: {e}")

    def _process_indexers(self, data: Any) -> list[Indexer]:
        """Process indexers JSON response.

        Only enabled torrent indexers supporting search are included.

        Args:
            data: Parsed JSON data from indexers endpoint

        Returns:
            List of Indexer objects

        Raises:
            ValueError: If response isn't list of indexers
        """
        if not isinstance(data, list):
            raise ValueError("Unexpected Prowlarr indexers response")

        indexers = []
        for indexer in data:
            if not isinstance(indexer, dict):
                continue
            indexer_id = indexer.get("id")
            indexer_name = indexer.get("name")
            if (
                not indexer_id
                or not indexer_name
                or not indexer.get("enable")
                or indexer.get("protocol") == "usenet"
                or indexer.get("supportsSearch") is False
            ):
                continue
            # Prefix with prowlarr: to distinguish from other providers
            indexers.append(
                Indexer(f"prowlarr:{indexer_id}", str(indexer_name), "Prowlarr")
            )
        return indexers

    def _build_search_url(
        self,
        query: str,
        categories: list[Category] | None,
        indexers: list[str] | None,
    ) -> str:
        """Build Prowlarr API search URL.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)
            indexers: Indexer IDs to search (optional)

        Returns:
            Complete URL with parameters
        """
        base_url = self.prowlarr_url.rstrip("/")
        endpoint = f"{base_url}/api/v1/search"

        # Build query parameters list (for repeated params)
        params_list = [("query", query.strip())]

        # Add indexer filter if specific indexers selected
        # Prowlarr expects multiple 'indexerIds' params, not comma-separated
        if indexers:
            for indexer_id in indexers:
                params_list.append(("indexerIds", indexer_id))

        # Add category filter if specified
        # Prowlarr expects multiple 'categories' params
        if categories:
            for cat in categories:
                params_list.append(("categories", str(cat.id)))

        return f"{endpoint}?{urllib.parse.urlencode(params_list)}"

    def _fetch_results(self, url: str) -> Any:
        """Fetch and parse JSON results from Prowlarr API.

        Args:
            url: Complete API URL

        Returns:
            Parsed JSON data as list

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            logger.debug(f"Prowlarr: requesting URL: {url}")
            with self.urlopen(url, headers=self._auth_headers()) as response:
                return json.loads(read_response(response).decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ""
            try:
                if e.fp:
                    error_body = e.fp.read(MAX_ERROR_BODY_SIZE).decode(
                        "utf-8", errors="replace"
                    )
                    logger.error(
                        f"Prowlarr HTTP {e.code} response: {error_body}"
                    )
            except Exception:
                pass
            if e.code in (401, 403):
                raise Exception("Invalid Prowlarr API key")
            # Search failure (e.g. all indexers unavailable) has message
            try:
                message = json.loads(error_body).get("message")
            except (ValueError, AttributeError):
                message = None
            raise Exception(f"HTTP error {e.code}: {message or e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Prowlarr at {self.prowlarr_url}: {e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Prowlarr response: {e}")

    def _process_results(self, data: Any) -> list[SearchResult]:
        """Process API response and convert to SearchResult list.

        Args:
            data: Parsed JSON response

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If response isn't list of results
        """
        if not isinstance(data, list):
            raise Exception("Failed to parse Prowlarr response: not a list")

        return [r for d in data if (r := self._parse_result(d))]

    def _parse_result(self, result: Any) -> SearchResult | None:
        """Parse a single result from Prowlarr API response.

        Args:
            result: Single result dict from Prowlarr API

        Returns:
            SearchResult or None if it's invalid or not a torrent
        """
        if not isinstance(result, dict):
            return None

        try:
            title = self._str(result.get("title"))
            # Usenet indexers return NZB files
            if not title or result.get("protocol") == "usenet":
                return None

            info_hash = parse_info_hash(result.get("infoHash"))
            magnet_link, torrent_link = self._extract_links(
                title, info_hash, result
            )

            # Skip result only if we have NEITHER link type
            if not magnet_link and not torrent_link:
                return None

            flags = result.get("indexerFlags")
            flags = flags if isinstance(flags, list) else []

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=torrent_link,
                provider=self._build_provider_name(result),
                provider_short=self._build_provider_name(result, short=True),
                provider_source="P",
                provider_id=self.id,
                categories=tuple(self._map_prowlarr_category(result) or ()),
                seeders=parse_count(result.get("seeders")),
                leechers=parse_count(result.get("leechers")),
                downloads=parse_count(result.get("grabs")),
                size=parse_count(result.get("size")),
                files_count=parse_count(result.get("files")),
                upload_date=local_time(
                    parse_iso_date(result.get("publishDate"))
                ),
                page_url=self._str(result.get("infoUrl")) or None,
                freeleech="freeleech" in flags,
                extra=self._build_fields(result),
            )
        except Exception:
            logger.exception(
                "Prowlarr: skipping invalid search result "
                f"{result.get('title')!r}"
            )
            return None

    def _extract_links(
        self, title: str, info_hash: str | None, result: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """Extract magnet and torrent links from result.

        Magnet link is magnet from guid, or Prowlarr magnetUrl (proxy link
        redirecting to magnet). Torrent link is Prowlarr downloadUrl (proxy
        link, which also works for private trackers), or .torrent link from
        guid. Magnet link built from info hash has no trackers, so it's
        used only without other links, as private torrents need trackers.

        Args:
            title: Torrent title (to add to built magnet link)
            info_hash: Torrent info hash (may be None)
            result: Result dict from Prowlarr API

        Returns:
            Tuple of (magnet link, torrent link), each may be None
        """
        guid = self._str(result.get("guid"))
        magnet_link = (
            guid if guid.startswith("magnet:") else None
        ) or self._str(result.get("magnetUrl"))
        torrent_link = self._str(result.get("downloadUrl")) or (
            guid if guid.endswith(".torrent") else None
        )

        if not magnet_link and not torrent_link and info_hash:
            magnet_link = build_magnet_link(info_hash=info_hash, name=title)

        return magnet_link or None, torrent_link or None

    def _str(self, value: Any) -> str:
        """Get string value from response, or empty string."""
        return value.strip() if isinstance(value, str) else ""

    def _build_provider_name(
        self, result: dict[str, Any], short: bool = False
    ) -> str:
        """Build provider name from indexer name.

        Args:
            result: Result dict from Prowlarr API
            short: Truncate name for compact view

        Returns:
            Provider name string (plain text)
        """
        indexer = str(result.get("indexer") or "Unknown")
        return indexer[:5] if short else indexer

    def _build_fields(self, result: dict[str, Any]) -> dict[str, object]:
        """Build provider-specific fields dict.

        Includes all fields from Prowlarr response except:
        - null/empty fields
        - fields already mapped to SearchResult main attributes

        Args:
            result: Result dict from Prowlarr API

        Returns:
            Dictionary of provider-specific fields
        """
        # Fields already mapped to SearchResult attributes
        excluded_fields = {
            "title",  # -> title
            "fileName",  # -> title
            "categories",  # -> categories (objects, not IDs)
            "seeders",  # -> seeders
            "leechers",  # -> leechers
            "grabs",  # -> downloads
            "size",  # -> size
            "files",  # -> files_count
            "magnetUrl",  # -> magnet_link
            "infoHash",  # -> info_hash
            "publishDate",  # -> upload_date
            "indexer",  # -> provider
            "indexerId",  # -> provider
            "infoUrl",  # -> page_url
            "guid",  # -> magnet_link or torrent_link
            "downloadUrl",  # -> torrent_link
            "protocol",  # only torrents are shown
            "id",  # internal field
            "sortTitle",  # internal field
            "age",  # -> publish_date
            "ageHours",  # -> publish_date
            "ageMinutes",  # -> publish_date
        }

        fields = {}
        for key, value in result.items():
            # Skip excluded fields
            if key in excluded_fields:
                continue

            # Skip null/empty values
            if value is None or value == "" or value == []:
                continue

            if isinstance(value, list):
                # Freeleech flag is shown as main field
                if key == "indexerFlags" and set(value) == {"freeleech"}:
                    continue
                fields[key] = ", ".join(str(v) for v in value)
            else:
                fields[key] = str(value)

        # Comments page is often the same as torrent page
        if fields.get("commentUrl") == result.get("infoUrl"):
            fields.pop("commentUrl", None)

        return fields

    def _map_prowlarr_category(self, result: dict[str, Any]) -> list[Category]:
        """Map Prowlarr category codes to Category objects.

        Prowlarr returns categories as array of objects with 'id' field.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            List of Category objects (may contain parent and subcategory)
        """
        category_objects = result.get("categories", [])
        if not category_objects:
            return []

        # Extract category IDs from category objects
        codes = []
        for cat_obj in category_objects:
            if isinstance(cat_obj, dict) and "id" in cat_obj:
                try:
                    codes.append(int(cat_obj["id"]))
                except (ValueError, TypeError):
                    pass

        if not codes:
            return []

        # Map codes to Category objects
        categories = []
        for code in codes:
            category = StandardCategories.get_by_id(code)
            if category:
                categories.append(category)

        return categories if categories else []

    def _transform_field(
        self, key: str, value: str
    ) -> tuple[str, str | DetailsLink] | None:
        """Transform field key and value for display.

        Args:
            key: Field name from Prowlarr response
            value: Field value

        Returns:
            Tuple of (display name, display value), where value is link
            for HTTP(S) URL, or None to hide field
        """
        if key == "imdbId":
            link = imdb_link(value)
            return ("IMDB", link) if link else None
        if key in ("tmdbId", "tvMazeId", "tvdbId") and value == "0":
            return None
        labels = {"indexerFlags": "Indexer Flags", "posterUrl": "Poster"}
        return labels.get(key, key), details_value(value)
