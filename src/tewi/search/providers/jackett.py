"""Jackett torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
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


class JackettProvider(BaseSearchProvider):
    """Search provider for Jackett (meta-indexer).

    Jackett provides unified access to multiple torrent indexers
    through a single API. Requires local Jackett instance.
    Documentation: https://github.com/Jackett/Jackett
    """

    def __init__(
        self,
        jackett_url: str | None = None,
        api_key: str | None = None,
        multi_indexer: bool = False,
    ):
        """Initialize Jackett provider with configuration.

        Args:
            jackett_url: Base URL of Jackett instance
            api_key: API key for Jackett authentication
            multi_indexer: If True, load all indexers individually.
                          If False, use single "all" endpoint (default)
        """
        self.jackett_url: str | None = jackett_url
        self.api_key: str | None = api_key
        self.multi_indexer: bool = multi_indexer
        self._config_error: str | None = self._validate_config(
            jackett_url, api_key
        )
        self._cached_indexers: list[Indexer] | None = None
        self._cache_time: datetime | None = None
        self._cache_duration: timedelta = timedelta(minutes=10)

    @property
    def id(self) -> str:
        return "jackett"

    @property
    def name(self) -> str:
        return "Jackett"

    def indexers(self) -> list[Indexer]:
        """Return list of configured indexers from Jackett instance.

        When multi_indexer is False, returns a single "Jackett" indexer
        that searches all indexers via the /all endpoint.

        When multi_indexer is True, fetches and returns all individual
        indexers. Uses a 10-minute cache to avoid repeated API calls.

        Returns:
            List of (indexer_id, indexer_name) tuples from Jackett,
            or empty list if not configured or error occurs
        """
        if self._config_error:
            logger.debug(f"Jackett not configured: {self._config_error}")
            return []

        # If multi_indexer is disabled, return single "Jackett" indexer
        if not self.multi_indexer:
            logger.debug("Jackett: multi_indexer disabled, returning single")
            return [Indexer(id="jackett:all", name="Jackett")]

        # Check if cache is valid
        if self._is_cache_valid():
            logger.debug("Jackett: returning cached indexers")
            return self._cached_indexers

        try:
            url = self._build_indexers_url()
            data = self._fetch_indexers(url)
            indexers = self._process_indexers(data)
            logger.info(f"Jackett: loaded {len(indexers)} indexers")

            # Update cache
            self._cached_indexers = indexers
            self._cache_time = datetime.now()

            return indexers
        except Exception as e:
            # Return empty list if indexers cannot be fetched
            logger.warning(f"Failed to load Jackett indexers: {e}")
            return []

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search Jackett for torrents across all indexers.

        Args:
            query: Search term
            categories: Category IDs to filter by (optional)
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

        # If multi_indexer is disabled, always use "all" endpoint
        if not self.multi_indexer:
            url = self._build_search_url(query, "all", categories)
            data = self._fetch_results(url)
            return self._process_results(data)

        # If specific indexers selected that differ from all indexers,
        # search each individually
        # (Jackett can search only on 1 or all indexers)
        if self._should_search_multiple_indexers(indexers):
            return self._search_multiple_indexers(query, categories, indexers)
        else:
            # Search all indexers
            url = self._build_search_url(query, "all", categories)
            data = self._fetch_results(url)
            return self._process_results(data)

    def details_extended(self, result: SearchResult) -> str:
        """Generate Jackett-specific details for right column.

        Prints all provider-specific fields from the search result.
        Applies transformations to enhance certain fields (e.g., IMDB).

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with Jackett details
        """
        if not result.fields:
            return ""

        md = "## Indexer Info\n"

        # Print all fields in sorted order for consistent display
        for key in sorted(result.fields.keys()):
            value = result.fields[key]
            # Transform field for display
            display_name, display_value = self._transform_field(key, value)
            md += f"- **{display_name}:** {display_value}\n"

        return md

    def fetch_from_indexer(
        self, query: str, indexer_id: str, categories: list[Category] | None
    ) -> list[SearchResult]:
        """Helper for parallel execution."""
        url = self._build_search_url(query, indexer_id, categories)
        data = self._fetch_results(url)
        return self._process_results(data)

    def _validate_config(
        self, jackett_url: str | None, api_key: str | None
    ) -> str | None:
        """Validate configuration and return error message if invalid.

        Args:
            jackett_url: Base URL of Jackett instance
            api_key: API key for Jackett authentication

        Returns:
            Error message string if invalid, None if valid
        """
        if not jackett_url or not jackett_url.strip():
            return (
                "Jackett URL not configured. "
                "Set jackett_url in [search] section."
            )
        if not api_key or not api_key.strip():
            return (
                "Jackett API key not configured. "
                "Set jackett_api_key in [search] section."
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
        """Build Jackett API indexers URL.

        Uses search results endpoint with empty query to get indexer list.
        This endpoint returns JSON with indexer information.

        Returns:
            Complete URL to fetch indexers list
        """
        base_url = self.jackett_url.rstrip("/")
        endpoint = f"{base_url}/api/v2.0/indexers/all/results"
        # Use non-existent category to prevent Jackett from actual search
        # and return empty search list and all indexers
        params = {"apikey": self.api_key, "cat": 123456}
        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    def _fetch_indexers(self, url: str) -> dict:
        """Fetch and parse JSON indexers list from Jackett API.

        Args:
            url: Complete API URL

        Returns:
            Parsed JSON data as dictionary

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            with urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Exception("Invalid Jackett API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Jackett at {self.jackett_url}: {e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Jackett JSON response: {e}")

    def _process_indexers(self, data: dict) -> list[Indexer]:
        """Process indexers JSON response.

        Args:
            data: Parsed JSON data from search endpoint

        Returns:
            List of Indexer objects
        """
        indexers = []

        # Get indexers list from response
        indexers_data = sorted(
            data.get("Indexers", []), key=lambda x: x["Name"]
        )

        for indexer in indexers_data:
            indexer_id = indexer.get("ID")
            indexer_name = indexer.get("Name")
            # Only include indexers with valid ID and Name
            if indexer_id and indexer_name:
                # Prefix with jackett: to distinguish from other providers
                full_id = f"jackett:{indexer_id}"
                indexers.append(
                    Indexer(full_id, f"{indexer_name} [dim](Jackett)[/]")
                )
        return indexers

    def _should_search_multiple_indexers(
        self, indexers: list[str] | None
    ) -> bool:
        """Check if selected indexers differ from all available indexers.

        Args:
            indexers: List of indexer IDs (without 'jackett:' prefix),
                     or None to search all indexers

        Returns:
            True if specific indexers are selected and they differ from all
            available indexers, False otherwise
        """
        # No indexers selected means search all
        if not indexers or len(indexers) == 0:
            return False

        # Get all available indexers
        all_indexers = self.indexers()
        if not all_indexers:
            return False

        # Extract indexer IDs without 'jackett:' prefix
        all_indexer_ids = set()
        for indexer in all_indexers:
            # Remove 'jackett:' prefix from ID
            indexer_id = indexer.id.replace("jackett:", "", 1)
            all_indexer_ids.add(indexer_id)

        # Compare selected indexers with all indexers
        selected_set = set(indexers)
        return selected_set != all_indexer_ids

    def _search_multiple_indexers(
        self,
        query: str,
        categories: list[Category] | None,
        indexers: list[str],
    ) -> list[SearchResult]:
        """Search multiple indexers individually and combine results.

        Args:
            query: Search term
            categories: Category IDs to filter by (optional)
            indexers: List of indexer IDs to search

        Returns:
            Combined list of SearchResult objects from all indexers
        """
        all_results = []

        with ThreadPoolExecutor(max_workers=len(indexers)) as executor:
            futures = {
                executor.submit(
                    self.fetch_from_indexer, query, indexer_id, categories
                ): indexer_id
                for indexer_id in indexers
            }

            for future in as_completed(futures):
                indexer_id = futures[future]
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    logger.warning(
                        f"Jackett indexer '{indexer_id}' failed: {e}"
                    )

        return all_results

    def _build_search_url(
        self, query: str, indexers: str, categories: list[Category] | None
    ) -> str:
        """Build Jackett API search URL.

        Args:
            query: Search term
            indexers: Indexer ID or 'all'

        Returns:
            Complete URL with parameters
        """
        base_url = self.jackett_url.rstrip("/")
        endpoint = f"{base_url}/api/v2.0/indexers/{indexers}/results"
        params = {
            "apikey": self.api_key,
            "Query": query.strip(),
        }

        # Add category filter if specified
        if categories:
            # Jackett accepts comma-separated category IDs (as strings)
            params["Category"] = ",".join(str(cat.id) for cat in categories)

        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    def _fetch_results(self, url: str) -> dict:
        """Fetch and parse JSON results from Jackett API.

        Args:
            url: Complete API URL

        Returns:
            Parsed JSON data

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            logger.debug(f"Jackett: requesting URL: {url}")
            with urlopen(url) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ""
            try:
                if e.fp:
                    error_body = e.fp.read().decode("utf-8")
                    logger.error(
                        f"Jackett HTTP {e.code} response: {error_body}"
                    )
            except Exception:
                pass
            if e.code in (401, 403):
                raise Exception("Invalid Jackett API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Jackett at {self.jackett_url}: {e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Jackett response: {e}")

    def _process_results(self, data: dict) -> list[SearchResult]:
        """Process API response and convert to SearchResult list.

        Args:
            data: Parsed JSON response

        Returns:
            List of SearchResult objects
        """
        results_data = data.get("Results", [])
        if not results_data:
            return []

        results = []
        for result_dict in results_data:
            result = self._parse_result(result_dict)
            if result:
                results.append(result)
        return results

    def _parse_result(self, result: dict[str, Any]) -> SearchResult | None:
        """Parse a single result from Jackett API response.

        Args:
            result: Single result dict from Jackett API

        Returns:
            SearchResult or None if parsing fails
        """
        try:
            title = result.get("Title")
            if not title:
                return None

            info_hash = result.get("InfoHash")

            # Extract both link types
            magnet_link = self._extract_magnet_link(title, info_hash, result)
            torrent_link = result.get("Link")

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
                categories=self._map_jackett_category(result),
                seeders=result.get("Seeders"),
                leechers=result.get("Peers"),
                downloads=result.get("Grabs"),
                size=result.get("Size"),
                files_count=result.get("Files"),
                upload_date=self._parse_upload_date(result),
                page_url=result.get("Details"),
                freeleech=result.get("DownloadVolumeFactor") == 0,
                fields=self._build_fields(result),
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _extract_magnet_link(
        self, title: str, info_hash: str | None, result: dict[str, Any]
    ) -> str | None:
        """Extract or generate magnet link from result.

        Priority: MagnetUri field → Generated from InfoHash → None

        Args:
            result: Result dict from Jackett API
            info_hash: Torrent info hash (may be None)

        Returns:
            Magnet URI string or None if unavailable
        """
        magnet_uri = result.get("MagnetUri")
        if magnet_uri:
            return magnet_uri

        # Generate magnet from info hash if available
        if info_hash:
            return build_magnet_link(info_hash=info_hash, name=title)

        return None

    def _parse_upload_date(self, result: dict[str, Any]) -> datetime | None:
        """Parse upload date from result.

        Args:
            result: Result dict from Jackett API

        Returns:
            datetime object or None if parsing fails
        """
        publish_date = result.get("PublishDate")
        if not publish_date:
            return None

        try:
            return datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _build_provider_name(self, result: dict[str, Any]) -> str:
        """Build provider name in format 'IndexerName (J)'.

        Args:
            result: Result dict from Jackett API

        Returns:
            Provider name string
        """
        tracker_id = result.get("TrackerId", "Unknown")
        tracker = result.get("Tracker", tracker_id)
        return f"{tracker} [dim](J)[/]"

    def _build_fields(self, result: dict[str, Any]) -> dict[str, str]:
        """Build provider-specific fields dict.

        Includes all fields from Jackett response except:
        - null/empty fields
        - fields already mapped to SearchResult main attributes

        Args:
            result: Result dict from Jackett API

        Returns:
            Dictionary of provider-specific fields
        """
        # Fields already mapped to SearchResult attributes
        excluded_fields = {
            "Title",  # -> title
            "Category",  # -> category (via _map_jackett_category)
            "Seeders",  # -> seeders
            "Peers",  # -> leechers
            "Grabs",  # -> downloads
            "Size",  # -> size
            "Files",  # -> files_count
            "MagnetUri",  # -> magnet_link
            "InfoHash",  # -> info_hash
            "PublishDate",  # -> upload_date
            "Tracker",  # -> provider (via _build_provider_name)
            "TrackerId",  # -> provider (via _build_provider_name)
            "Details",  # -> page_url
            "Comments",  # -> page_url (fallback)
            "Link",  # -> torrent_link
            "Guid",  # ignore
            "FirstSeen",  # ignore
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
            if isinstance(value, (list, dict)):
                # For complex types, convert to string
                fields[key] = str(value)
            else:
                fields[key] = str(value)

        return fields if fields else None

    def _map_jackett_category(
        self, result: dict[str, Any]
    ) -> list[Category] | None:
        """Map Jackett category codes to Category objects.

        Jackett uses Torznab category IDs with hierarchy:
        - Parent categories end in 000 (e.g., 2000 = Movies)
        - Subcategories have specific IDs (e.g., 2040 = Movies/HD)

        Args:
            result: Result dict from Jackett API

        Returns:
            List of Category objects (may contain parent and subcategory)
        """
        category_codes = result.get("Category")
        if not category_codes:
            return None

        # Get all category codes from the result
        codes = self._extract_category_codes(category_codes)
        if not codes:
            return None

        # Map codes to Category objects
        categories = []
        for code in codes:
            category = StandardCategories.get_by_id(code)
            if category:
                categories.append(category)

        return categories

    def _extract_category_codes(self, category_codes: Any) -> list[int]:
        """Extract all category codes from Jackett response.

        Args:
            category_codes: Category codes (list or single value)

        Returns:
            List of category codes as integers
        """
        codes = []
        try:
            if isinstance(category_codes, list):
                for code in category_codes:
                    codes.append(int(code))
            else:
                codes.append(int(category_codes))
        except (ValueError, TypeError):
            pass
        return codes

    def _transform_field(self, key: str, value: str) -> tuple[str, str]:
        """Transform field key and value for display.

        Applies transformations like converting IDs to URLs.
        This is a universal mechanism for enhancing field display.

        Args:
            key: Field name from Jackett response
            value: Field value

        Returns:
            Tuple of (display_name, display_value)
        """
        if key == "CategoryDesc":
            return "Category", value
        elif key == "Imdb":
            return "IMDB", f"https://www.imdb.com/title/tt{value}/"

        return key, value
