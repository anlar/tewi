"""Jackett torrent search provider implementation."""

import logging
import urllib.error
import urllib.parse
import json
from datetime import datetime, timedelta
from typing import Any

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, Category, JackettCategories, IndexerDTO
from ...util.decorator import log_time

logger = logging.getLogger('tewi')


class JackettProvider(BaseSearchProvider):
    """Search provider for Jackett (meta-indexer).

    Jackett provides unified access to multiple torrent indexers
    through a single API. Requires local Jackett instance.
    Documentation: https://github.com/Jackett/Jackett
    """

    def __init__(self,
                 jackett_url: str | None = None,
                 api_key: str | None = None):
        """Initialize Jackett provider with configuration.

        Args:
            jackett_url: Base URL of Jackett instance
            api_key: API key for Jackett authentication
        """
        self.jackett_url = jackett_url
        self.api_key = api_key
        self._config_error = self._validate_config(jackett_url, api_key)
        self._selected_indexers: list[str] | None = None
        self._selected_categories: list[Category] | None = None
        self._cached_indexers: list[IndexerDTO] | None = None
        self._cache_time: datetime | None = None
        self._cache_duration = timedelta(minutes=10)

    def _validate_config(self,
                         jackett_url: str | None,
                         api_key: str | None) -> str | None:
        """Validate configuration and return error message if invalid.

        Args:
            jackett_url: Base URL of Jackett instance
            api_key: API key for Jackett authentication

        Returns:
            Error message string if invalid, None if valid
        """
        if not jackett_url or not jackett_url.strip():
            return ("Jackett URL not configured. "
                    "Set jackett_url in [search] section.")
        if not api_key or not api_key.strip():
            return ("Jackett API key not configured. "
                    "Set jackett_api_key in [search] section.")
        return None

    def id(self) -> str:
        return "jackett"

    def indexers(self) -> list[IndexerDTO]:
        """Return list of configured indexers from Jackett instance.

        Uses a 10-minute cache to avoid repeated API calls.

        Returns:
            List of (indexer_id, indexer_name) tuples from Jackett,
            or empty list if not configured or error occurs
        """
        if self._config_error:
            logger.debug(f"Jackett not configured: {self._config_error}")
            return []

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
        base_url = self.jackett_url.rstrip('/')
        endpoint = f"{base_url}/api/v2.0/indexers/all/results"
        params = {
            'apikey': self.api_key,
            'Query': ''
        }
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
            with self._urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Exception("Invalid Jackett API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Jackett at {self.jackett_url}: "
                f"{e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Jackett JSON response: {e}")

    def _process_indexers(self, data: dict) -> list[IndexerDTO]:
        """Process indexers JSON response.

        Args:
            data: Parsed JSON data from search endpoint

        Returns:
            List of IndexerDTO objects
        """
        indexers = []

        # Get indexers list from response
        indexers_data = sorted(data.get('Indexers', []), key=lambda x: x['Name'])

        for indexer in indexers_data:
            indexer_id = indexer.get('ID')
            indexer_name = indexer.get('Name')
            # Only include indexers with valid ID and Name
            if indexer_id and indexer_name:
                # Prefix with jackett: to distinguish from other providers
                full_id = f"jackett:{indexer_id}"
                indexers.append(IndexerDTO(
                    full_id,
                    f"{indexer_name} [dim](Jackett)[/]"))
        return indexers

    @property
    def name(self) -> str:
        return "Jackett"

    @log_time
    def _search_impl(self, query: str,
                     categories: list[Category] | None = None) -> list[
            SearchResultDTO]:
        """Search Jackett for torrents across all indexers.

        Args:
            query: Search term
            categories: Category IDs to filter by (optional)

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If API request fails or not configured
        """
        if self._config_error:
            raise Exception(self._config_error)

        if not query or not query.strip():
            return []

        # Store categories for use in URL building
        self._selected_categories = categories

        # If specific indexers selected, search each individually
        # (Jackett has bug with comma-separated indexers in URL)
        if self._selected_indexers and len(self._selected_indexers) > 0:
            return self._search_multiple_indexers(query)

        # Search all indexers
        url = self._build_search_url(query, 'all')
        data = self._fetch_results(url)
        return self._process_results(data)

    def _search_multiple_indexers(
            self,
            query: str) -> list[SearchResultDTO]:
        """Search multiple indexers individually and combine results.

        Workaround for Jackett bug where comma-separated indexers
        in URL path cause NullReferenceException.

        Args:
            query: Search term

        Returns:
            Combined list of SearchResultDTO objects from all indexers
        """
        all_results = []
        for indexer_id in self._selected_indexers:
            try:
                url = self._build_search_url(query, indexer_id)
                data = self._fetch_results(url)
                results = self._process_results(data)
                all_results.extend(results)
            except Exception as e:
                # Log error but continue with other indexers
                logger.warning(
                    f"Jackett indexer '{indexer_id}' failed: {e}")
        return all_results

    def set_selected_indexers(self, indexer_ids: list[str] | None) -> None:
        """Set which indexers to search.

        Args:
            indexer_ids: List of indexer IDs (without 'jackett:' prefix),
                        or None to search all indexers
        """
        self._selected_indexers = indexer_ids

    def _build_search_url(self, query: str, indexers: str) -> str:
        """Build Jackett API search URL.

        Args:
            query: Search term
            indexers: Indexer ID or 'all'

        Returns:
            Complete URL with parameters
        """
        base_url = self.jackett_url.rstrip('/')
        endpoint = f"{base_url}/api/v2.0/indexers/{indexers}/results"
        params = {
            'apikey': self.api_key,
            'Query': query.strip(),
        }

        # Add category filter if specified
        if self._selected_categories:
            # Jackett accepts comma-separated category IDs (as strings)
            params['Category'] = ','.join(
                str(cat.id) for cat in self._selected_categories)

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
            with self._urlopen(url) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ''
            try:
                if e.fp:
                    error_body = e.fp.read().decode('utf-8')
                    logger.error(f"Jackett HTTP {e.code} response: "
                                 f"{error_body}")
            except Exception:
                pass
            if e.code in (401, 403):
                raise Exception("Invalid Jackett API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Jackett at {self.jackett_url}: "
                f"{e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Jackett response: {e}")

    def _process_results(self, data: dict) -> list[SearchResultDTO]:
        """Process API response and convert to SearchResultDTO list.

        Args:
            data: Parsed JSON response

        Returns:
            List of SearchResultDTO objects
        """
        results_data = data.get('Results', [])
        if not results_data:
            return []

        results = []
        for result_dict in results_data:
            result = self._parse_result(result_dict)
            if result:
                results.append(result)
        return results

    def _parse_result(self,
                      result: dict[str, Any]) -> SearchResultDTO | None:
        """Parse a single result from Jackett API response.

        Args:
            result: Single result dict from Jackett API

        Returns:
            SearchResultDTO or None if parsing fails
        """
        try:
            # Allow None for info_hash
            info_hash_raw = result.get('InfoHash', '')
            info_hash = info_hash_raw.strip() if info_hash_raw else None
            if info_hash == '':
                info_hash = None

            # Extract both link types
            magnet_link = self._extract_magnet_link(result, info_hash)
            torrent_link = self._extract_torrent_link(result)

            # Skip result only if we have NEITHER link type
            if not magnet_link and not torrent_link:
                return None

            return SearchResultDTO(
                title=result.get('Title', 'Unknown'),
                categories=self._map_jackett_category(result),
                seeders=int(result.get('Seeders')),
                leechers=int(result.get('Peers')),
                size=int(result.get('Size')),
                files_count=self._get_files_count(result),
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=self._parse_upload_date(result),
                provider=self._build_provider_name(result),
                provider_id=self.id(),
                page_url=self._get_page_url(result),
                torrent_link=torrent_link,
                fields=self._build_fields(result)
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _extract_magnet_link(self,
                             result: dict[str, Any],
                             info_hash: str | None) -> str | None:
        """Extract or generate magnet link from result.

        Priority: MagnetUri field → Generated from InfoHash → None

        Args:
            result: Result dict from Jackett API
            info_hash: Torrent info hash (may be None)

        Returns:
            Magnet URI string or None if unavailable
        """
        magnet_uri_raw = result.get('MagnetUri', '')
        magnet_uri = magnet_uri_raw.strip() if magnet_uri_raw else ''
        if magnet_uri:
            return magnet_uri

        # Generate magnet from info hash if available
        if info_hash:
            return self._build_magnet_link(
                info_hash=info_hash,
                name=result.get('Title', 'Unknown')
            )

        return None

    def _extract_torrent_link(self,
                              result: dict[str, Any]) -> str | None:
        """Extract HTTP/HTTPS torrent file URL from result.

        Args:
            result: Result dict from Jackett API

        Returns:
            HTTP/HTTPS URL or None if unavailable
        """
        link_raw = result.get('Link', '')
        link = link_raw.strip() if link_raw else ''
        if link and (link.startswith('http://') or
                     link.startswith('https://')):
            return link
        return None

    def _parse_upload_date(self,
                           result: dict[str, Any]) -> datetime | None:
        """Parse upload date from result.

        Args:
            result: Result dict from Jackett API

        Returns:
            datetime object or None if parsing fails
        """
        publish_date = result.get('PublishDate')
        if not publish_date:
            return None

        try:
            return datetime.fromisoformat(
                publish_date.replace('Z', '+00:00')
            )
        except (ValueError, AttributeError):
            return None

    def _build_provider_name(self, result: dict[str, Any]) -> str:
        """Build provider name in format 'IndexerName (J)'.

        Args:
            result: Result dict from Jackett API

        Returns:
            Provider name string
        """
        tracker_id = result.get('TrackerId', 'Unknown')
        tracker = result.get('Tracker', tracker_id)
        return f"{tracker} [dim](J)[/]"

    def _get_page_url(self, result: dict[str, Any]) -> str | None:
        """Get page URL from result.

        Args:
            result: Result dict from Jackett API

        Returns:
            Page URL or None
        """
        return result.get('Details') or result.get('Comments')

    def _get_files_count(self, result: dict[str, Any]) -> int | None:
        """Get file count from result.

        Args:
            result: Result dict from Jackett API

        Returns:
            File count as integer or None
        """
        files_count = result.get('Files')
        if files_count is not None:
            return int(files_count)
        return None

    def _build_fields(self, result: dict[str, Any]) -> dict[str, str]:
        """Build provider-specific fields dict.

        Includes all fields from Jackett response except:
        - null/empty fields
        - fields already mapped to SearchResultDTO main attributes

        Args:
            result: Result dict from Jackett API

        Returns:
            Dictionary of provider-specific fields
        """
        # Fields already mapped to SearchResultDTO attributes
        excluded_fields = {
            'Title',           # -> title
            'Category',        # -> category (via _map_jackett_category)
            'Seeders',         # -> seeders
            'Peers',           # -> leechers
            'Size',            # -> size
            'Files',           # -> files_count
            'MagnetUri',       # -> magnet_link
            'InfoHash',        # -> info_hash
            'PublishDate',     # -> upload_date
            'Tracker',         # -> provider (via _build_provider_name)
            'TrackerId',       # -> provider (via _build_provider_name)
            'Details',         # -> page_url
            'Comments',        # -> page_url (fallback)
            'Link',            # -> torrent_link
            'Guid',            # ignore
            'FirstSeen'        # ignore
        }

        fields = {}
        for key, value in result.items():
            # Skip excluded fields
            if key in excluded_fields:
                continue

            # Skip null/empty values
            if value is None or value == '' or value == []:
                continue

            # Convert to string representation
            if isinstance(value, (list, dict)):
                # For complex types, convert to string
                fields[key] = str(value)
            else:
                fields[key] = str(value)

        return fields if fields else None

    def _map_jackett_category(self,
                              result: dict[str, Any]) -> list[Category]:
        """Map Jackett category codes to Category objects.

        Jackett uses Torznab category IDs with hierarchy:
        - Parent categories end in 000 (e.g., 2000 = Movies)
        - Subcategories have specific IDs (e.g., 2040 = Movies/HD)

        Args:
            result: Result dict from Jackett API

        Returns:
            List of Category objects (may contain parent and subcategory)
        """
        category_codes = result.get('Category', [])
        if not category_codes:
            return []

        # Get all category codes from the result
        codes = self._extract_category_codes(category_codes)
        if not codes:
            return []

        # Map codes to Category objects
        categories = []
        for code in codes:
            category = JackettCategories.get_by_id(code)
            if category:
                categories.append(category)

        return categories if categories else []

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
        if key == 'CategoryDesc':
            return 'Category', value
        elif key == 'Imdb':
            return 'IMDB', f"https://www.imdb.com/title/tt{value}/"

        return key, value

    def details_extended(self, result: SearchResultDTO) -> str:
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
