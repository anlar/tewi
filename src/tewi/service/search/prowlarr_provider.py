"""Prowlarr torrent search provider implementation."""

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


class ProwlarrProvider(BaseSearchProvider):
    """Search provider for Prowlarr (meta-indexer).

    Prowlarr provides unified access to multiple torrent indexers
    through a single API. Requires local Prowlarr instance.
    Documentation: https://github.com/Prowlarr/Prowlarr
    """

    def __init__(self,
                 prowlarr_url: str | None = None,
                 api_key: str | None = None):
        """Initialize Prowlarr provider with configuration.

        Args:
            prowlarr_url: Base URL of Prowlarr instance
            api_key: API key for Prowlarr authentication
        """
        self.prowlarr_url = prowlarr_url
        self.api_key = api_key

        self._config_error = self._validate_config(prowlarr_url, api_key)

        self._selected_indexers: list[str] | None = None
        self._selected_categories: list[Category] | None = None

        self._cached_indexers: list[IndexerDTO] | None = None
        self._cache_time: datetime | None = None
        self._cache_duration = timedelta(minutes=10)

    def _validate_config(self,
                         prowlarr_url: str | None,
                         api_key: str | None) -> str | None:
        """Validate configuration and return error message if invalid.

        Args:
            prowlarr_url: Base URL of Prowlarr instance
            api_key: API key for Prowlarr authentication

        Returns:
            Error message string if invalid, None if valid
        """
        if not prowlarr_url or not prowlarr_url.strip():
            return ("Prowlarr URL not configured. "
                    "Set prowlarr_url in [search] section.")
        if not api_key or not api_key.strip():
            return ("Prowlarr API key not configured. "
                    "Set prowlarr_api_key in [search] section.")
        return None

    def id(self) -> str:
        return "prowlarr"

    def indexers(self) -> list[IndexerDTO]:
        """Return list of configured indexers from Prowlarr instance.

        Uses a 10-minute cache to avoid repeated API calls.

        Returns:
            List of IndexerDTO objects from Prowlarr,
            or empty list if not configured or error occurs
        """
        if self._config_error:
            logger.debug(f"Prowlarr not configured: {self._config_error}")
            return []

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
        base_url = self.prowlarr_url.rstrip('/')
        endpoint = f"{base_url}/api/v1/indexer"
        params = {'apikey': self.api_key}
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
            with self._urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Exception("Invalid Prowlarr API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Prowlarr at {self.prowlarr_url}: "
                f"{e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Prowlarr JSON response: {e}")

    def _process_indexers(self, data: list) -> list[IndexerDTO]:
        """Process indexers JSON response.

        Args:
            data: Parsed JSON data from indexers endpoint

        Returns:
            List of IndexerDTO objects
        """
        indexers = []

        # Sort indexers by name
        indexers_data = sorted(data, key=lambda x: x.get('name', ''))

        for indexer in indexers_data:
            indexer_id = indexer.get('id')
            indexer_name = indexer.get('name')
            # Only include enabled indexers with valid ID and Name
            enable = indexer.get('enable', False)
            if indexer_id and indexer_name and enable:
                # Prefix with prowlarr: to distinguish from other providers
                full_id = f"prowlarr:{indexer_id}"
                indexers.append(IndexerDTO(
                    full_id,
                    f"{indexer_name} [dim](Prowlarr)[/]"))
        return indexers

    @property
    def name(self) -> str:
        return "Prowlarr"

    @log_time
    def _search_impl(self, query: str,
                     categories: list[Category] | None = None) -> list[
            SearchResultDTO]:
        """Search Prowlarr for torrents across indexers.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)

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

        # Build URL with optional indexer filtering
        url = self._build_search_url(query)
        data = self._fetch_results(url)
        return self._process_results(data)

    def set_selected_indexers(self, indexer_ids: list[str] | None) -> None:
        """Set which indexers to search.

        Args:
            indexer_ids: List of indexer IDs (without 'prowlarr:' prefix),
                        or None to search all indexers
        """
        self._selected_indexers = indexer_ids

    def _build_search_url(self, query: str) -> str:
        """Build Prowlarr API search URL.

        Args:
            query: Search term

        Returns:
            Complete URL with parameters
        """
        base_url = self.prowlarr_url.rstrip('/')
        endpoint = f"{base_url}/api/v1/search"

        # Build query parameters list (for repeated params)
        params_list = [
            ('apikey', self.api_key),
            ('query', query.strip()),
        ]

        # Add indexer filter if specific indexers selected
        # Prowlarr expects multiple 'indexerIds' params, not comma-separated
        if self._selected_indexers:
            for indexer_id in self._selected_indexers:
                params_list.append(('indexerIds', indexer_id))

        # Add category filter if specified
        # Prowlarr expects multiple 'categories' params
        if self._selected_categories:
            for cat in self._selected_categories:
                params_list.append(('categories', str(cat.id)))

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
            with self._urlopen(url) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ''
            try:
                if e.fp:
                    error_body = e.fp.read().decode('utf-8')
                    logger.error(f"Prowlarr HTTP {e.code} response: "
                                 f"{error_body}")
            except Exception:
                pass
            if e.code in (401, 403):
                raise Exception("Invalid Prowlarr API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Prowlarr at {self.prowlarr_url}: "
                f"{e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Prowlarr response: {e}")

    def _process_results(self, data: list) -> list[SearchResultDTO]:
        """Process API response and convert to SearchResultDTO list.

        Args:
            data: Parsed JSON response as list

        Returns:
            List of SearchResultDTO objects
        """
        if not data:
            return []

        results = []
        for result_dict in data:
            result = self._parse_result(result_dict)
            if result:
                results.append(result)
        return results

    def _parse_result(self,
                      result: dict[str, Any]) -> SearchResultDTO | None:
        """Parse a single result from Prowlarr API response.

        Args:
            result: Single result dict from Prowlarr API

        Returns:
            SearchResultDTO or None if parsing fails
        """
        try:
            # Allow None for info_hash
            info_hash_raw = result.get('infoHash', '')
            info_hash = info_hash_raw.strip() if info_hash_raw else None
            if info_hash == '':
                info_hash = None

            # Extract both link types
            magnet_link = self._extract_magnet_link(result, info_hash)
            torrent_link = self._extract_torrent_link(result)

            # Skip result only if we have NEITHER link type
            if not magnet_link and not torrent_link:
                return None

            # Detect freeleech
            freeleech = 'freeleech' in result.get('indexerFlags')

            # Extract downloads from grabs field
            downloads = None
            grabs = result.get('grabs')
            if grabs is not None:
                downloads = int(grabs)

            return SearchResultDTO(
                title=result.get('title', 'Unknown'),
                categories=self._map_prowlarr_category(result),
                seeders=int(result.get('seeders', 0)),
                leechers=int(result.get('leechers', 0)),
                downloads=downloads,
                size=int(result.get('size', 0)),
                files_count=self._get_files_count(result),
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=self._parse_publish_date(result),
                provider=self._build_provider_name(result),
                provider_id=self.id(),
                page_url=self._get_page_url(result),
                torrent_link=torrent_link,
                freeleech=freeleech,
                fields=self._build_fields(result)
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _extract_magnet_link(self,
                             result: dict[str, Any],
                             info_hash: str | None) -> str | None:
        """Extract or generate magnet link from result.

        Priority: guid field (if magnet) → Generated from infoHash → None

        Args:
            result: Result dict from Prowlarr API
            info_hash: Torrent info hash (may be None)

        Returns:
            Magnet URI string or None if unavailable
        """
        # Prowlarr puts the actual magnet link in 'guid' field
        guid_raw = result.get('guid', '')
        guid = guid_raw.strip() if guid_raw else ''
        if guid and guid.startswith('magnet:'):
            return guid

        # Generate magnet from info hash if available
        if info_hash:
            return self._build_magnet_link(
                info_hash=info_hash,
                name=result.get('title', 'Unknown')
            )

        return None

    def _extract_torrent_link(self,
                              result: dict[str, Any]) -> str | None:
        """Extract HTTP/HTTPS torrent file URL from result.

        Prowlarr provides magnetUrl as a download proxy link.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            HTTP/HTTPS URL or None if unavailable
        """
        # Try downloadUrl first (if exists)
        link_raw = result.get('downloadUrl', '')
        link = link_raw.strip() if link_raw else ''
        if link and (link.startswith('http://') or
                     link.startswith('https://')):
            return link

        # Fall back to magnetUrl (Prowlarr's download proxy)
        magnet_url_raw = result.get('magnetUrl', '')
        magnet_url = magnet_url_raw.strip() if magnet_url_raw else ''
        if magnet_url and (magnet_url.startswith('http://') or
                           magnet_url.startswith('https://')):
            return magnet_url

        return None

    def _parse_publish_date(self,
                            result: dict[str, Any]) -> datetime | None:
        """Parse publish date from result.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            datetime object or None if parsing fails
        """
        publish_date = result.get('publishDate')
        if not publish_date:
            return None

        try:
            return datetime.fromisoformat(
                publish_date.replace('Z', '+00:00')
            )
        except (ValueError, AttributeError):
            return None

    def _build_provider_name(self, result: dict[str, Any]) -> str:
        """Build provider name in format 'IndexerName (Prowlarr)'.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            Provider name string
        """
        indexer = result.get('indexer', 'Unknown')
        return f"{indexer} [dim](P)[/]"

    def _get_page_url(self, result: dict[str, Any]) -> str | None:
        """Get page URL from result.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            Page URL or None
        """
        return result.get('infoUrl')

    def _get_files_count(self, result: dict[str, Any]) -> int | None:
        """Get file count from result.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            File count as integer or None
        """
        files_count = result.get('files')
        if files_count is not None:
            return int(files_count)
        return None

    def _build_fields(self, result: dict[str, Any]) -> dict[str, str]:
        """Build provider-specific fields dict.

        Includes all fields from Prowlarr response except:
        - null/empty fields
        - fields already mapped to SearchResultDTO main attributes

        Args:
            result: Result dict from Prowlarr API

        Returns:
            Dictionary of provider-specific fields
        """
        # Fields already mapped to SearchResultDTO attributes
        excluded_fields = {
            'title',           # -> title
            'fileName',        # -> title
            'categories',      # -> categories (objects, not IDs)
            'seeders',         # -> seeders
            'leechers',        # -> leechers
            'grabs',           # -> downloads
            'size',            # -> size
            'files',           # -> files_count
            'magnetUrl',       # -> torrent_link
            'infoHash',        # -> info_hash
            'publishDate',     # -> upload_date
            'indexer',         # -> provider
            'indexerId',       # -> provider
            'infoUrl',         # -> page_url
            'guid',            # -> magnet_link (actual magnet)
            'downloadUrl',     # -> torrent_link
            'sortTitle',       # internal field
            'age',             # -> publish_date
            'ageHours',        # -> publish_date
            'ageMinutes',      # -> publish_date
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
                fields[key] = value

        return fields if fields else None

    def _map_prowlarr_category(self,
                               result: dict[str, Any]) -> list[Category]:
        """Map Prowlarr category codes to Category objects.

        Prowlarr returns categories as array of objects with 'id' field.

        Args:
            result: Result dict from Prowlarr API

        Returns:
            List of Category objects (may contain parent and subcategory)
        """
        category_objects = result.get('categories', [])
        if not category_objects:
            return []

        # Extract category IDs from category objects
        codes = []
        for cat_obj in category_objects:
            if isinstance(cat_obj, dict) and 'id' in cat_obj:
                try:
                    codes.append(int(cat_obj['id']))
                except (ValueError, TypeError):
                    pass

        if not codes:
            return []

        # Map codes to Category objects
        categories = []
        for code in codes:
            category = JackettCategories.get_by_id(code)
            if category:
                categories.append(category)

        return categories if categories else []

    def _transform_field(self, key: str, value: str) -> tuple[str, str] | None:
        """Transform field key and value for display.

        Applies transformations like converting IDs to URLs.
        This is a universal mechanism for enhancing field display.

        Args:
            key: Field name from Jackett response
            value: Field value

        Returns:
            Tuple of (display_name, display_value)
        """
        if key == 'imdbId':
            if value:
                return 'IMDB', f"https://www.imdb.com/title/tt{value}/"
            else:
                return None, None
        elif key in ['tmdbId', 'tvMazeId', 'tvdbId']:
            if not value:
                return None, None
        elif key in ['protocol']:
            return key.capitalize(), value
        elif key == 'indexerFlags':
            return 'Indexer Flags', value
        elif key == 'posterUrl':
            return 'Poster', value

        return key, value

    def details_extended(self, result: SearchResultDTO) -> str:
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
