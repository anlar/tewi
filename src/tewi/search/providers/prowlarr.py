"""Prowlarr torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from typing import Any

from ...util.log import get_logger, log_time
from ..base import BaseSearchProvider
from ..models import Category, Indexer, SearchResult, StandardCategories
from ..util import (
    build_magnet_link,
    urlopen,
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
    ):
        """Initialize Prowlarr provider with configuration.

        Args:
            prowlarr_url: Base URL of Prowlarr instance
            api_key: API key for Prowlarr authentication
            multi_indexer: If True, load all indexers individually.
                          If False, use single "all" endpoint (default)
        """
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

        # If multi_indexer is disabled, ignore indexers parameter and search all
        if not self.multi_indexer:
            indexers = None

        # Build URL with optional indexer and category filtering
        url = self._build_search_url(query, categories, indexers)
        data = self._fetch_results(url)
        return self._process_results(data)

    def details_extended(self, result: SearchResult) -> str:
        """Generate Prowlarr-specific details for right column.

        Prints all provider-specific fields from the search result.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with Prowlarr details
        """
        if not result.fields:
            return ""

        md = "## Indexer Info\n"

        # Print all fields in sorted order for consistent display
        for key in sorted(result.fields.keys()):
            value = result.fields[key]
            # Transform field for display
            display_name, display_value = self._transform_field(key, value)
            if display_name:
                md += f"- **{display_name}:** {display_value}\n"

        return md

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
        endpoint = f"{base_url}/api/v1/indexer"
        params = {"apikey": self.api_key}
        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    def _fetch_indexers(self, url: str) -> list:
        """Fetch and parse JSON indexers list from Prowlarr API.

        Args:
            url: Complete API URL

        Returns:
            Parsed JSON data as list

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            with urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
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

    def _process_indexers(self, data: list) -> list[Indexer]:
        """Process indexers JSON response.

        Args:
            data: Parsed JSON data from indexers endpoint

        Returns:
            List of Indexer objects
        """
        indexers = []

        # Sort indexers by name
        indexers_data = sorted(data, key=lambda x: x.get("name", ""))

        for indexer in indexers_data:
            indexer_id = indexer.get("id")
            indexer_name = indexer.get("name")
            # Only include enabled indexers with valid ID and Name
            enable = indexer.get("enable", False)
            if indexer_id and indexer_name and enable:
                # Prefix with prowlarr: to distinguish from other providers
                full_id = f"prowlarr:{indexer_id}"
                indexers.append(
                    Indexer(full_id, f"{indexer_name} [dim](Prowlarr)[/]")
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
        params_list = [
            ("apikey", self.api_key),
            ("query", query.strip()),
        ]

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

    def _fetch_results(self, url: str) -> list:
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
            with urlopen(url) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ""
            try:
                if e.fp:
                    error_body = e.fp.read().decode("utf-8")
                    logger.error(
                        f"Prowlarr HTTP {e.code} response: {error_body}"
                    )
            except Exception:
                pass
            if e.code in (401, 403):
                raise Exception("Invalid Prowlarr API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Prowlarr at {self.prowlarr_url}: {e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Prowlarr response: {e}")

    def _process_results(self, data: list) -> list[SearchResult]:
        """Process API response and convert to SearchResult list.

        Args:
            data: Parsed JSON response as list

        Returns:
            List of SearchResult objects
        """
        if not data:
            return []

        results = []
        for result_dict in data:
            result = self._parse_result(result_dict)
            if result:
                results.append(result)
        return results

    def _parse_result(self, result: dict[str, Any]) -> SearchResult | None:
        """Parse a single result from Prowlarr API response.

        Args:
            result: Single result dict from Prowlarr API

        Returns:
            SearchResult or None if parsing fails
        """
        try:
            title = result.get("title")
            if not title:
                return None

            info_hash = result.get("infoHash")

            # Extract both link types
            magnet_link = self._extract_magnet_link(title, info_hash, result)
            torrent_link = (result.get("magnetUrl"),)

            # Skip result only if we have NEITHER link type
            if not magnet_link and not torrent_link:
                return None

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=torrent_link,
                provider=self._build_provider_name(result),
                provider_id=self.id,
                categories=self._map_prowlarr_category(result),
                seeders=result.get("seeders"),
                leechers=result.get("leechers"),
                downloads=result.get("grabs"),
                size=result.get("size"),
                files_count=result.get("files"),
                upload_date=self._parse_publish_date(result),
                page_url=result.get("infoUrl"),
                freeleech="freeleech" in result.get("indexerFlags"),
                fields=self._build_fields(result),
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _extract_magnet_link(
        self, title: str, info_hash: str | None, result: dict[str, Any]
    ) -> str | None:
        """Extract or generate magnet link from result.

        Priority: guid field (if magnet) → Generated from infoHash → None

        Args:
            result: Result dict from Prowlarr API
            info_hash: Torrent info hash (may be None)

        Returns:
            Magnet URI string or None if unavailable
        """
        # Prowlarr puts the actual magnet link in 'guid' field
        guid = result.get("guid")
        if guid and guid.startswith("magnet:"):
            return guid

        # Generate magnet from info hash if available
        if info_hash:
            return build_magnet_link(info_hash=info_hash, name=title)

        return None

    def _parse_publish_date(self, result: dict[str, Any]) -> datetime | None:
        """Parse publish date from result.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            datetime object or None if parsing fails
        """
        publish_date = result.get("publishDate")
        if not publish_date:
            return None

        try:
            return datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _build_provider_name(self, result: dict[str, Any]) -> str:
        """Build provider name in format 'IndexerName (Prowlarr)'.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            Provider name string
        """
        indexer = result.get("indexer", "Unknown")
        return f"{indexer} [dim](P)[/]"

    def _build_fields(self, result: dict[str, Any]) -> dict[str, str]:
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
            "magnetUrl",  # -> torrent_link
            "infoHash",  # -> info_hash
            "publishDate",  # -> upload_date
            "indexer",  # -> provider
            "indexerId",  # -> provider
            "infoUrl",  # -> page_url
            "guid",  # -> magnet_link (actual magnet)
            "downloadUrl",  # -> torrent_link
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

            # Convert to string representation
            if isinstance(value, list):
                # skip, if flags contains only freelech
                if key == "indexerFlags" and set(value) == {"freeleech"}:
                    continue
                else:
                    # For complex types, convert to string
                    fields[key] = ",".join(value)
            else:
                fields[key] = value

        return fields if fields else None

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

    def _transform_field(self, key: str, value: str) -> tuple[str, str] | None:
        """Transform field key and value for display.

        Applies transformations like converting IDs to URLs.
        This is a universal mechanism for enhancing field display.

        Args:
            key: Field name from Prowlarr response
            value: Field value

        Returns:
            Tuple of (display_name, display_value)
        """
        if key == "imdbId":
            if value:
                return "IMDB", f"https://www.imdb.com/title/tt{value}/"
            else:
                return None, None
        elif key in ["tmdbId", "tvMazeId", "tvdbId"]:
            if not value:
                return None, None
        elif key in ["protocol"]:
            return key.capitalize(), value
        elif key == "indexerFlags":
            return "Indexer Flags", value
        elif key == "posterUrl":
            return "Poster", value

        return key, value
