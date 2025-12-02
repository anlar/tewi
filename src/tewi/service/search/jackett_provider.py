"""Jackett torrent search provider implementation."""

import urllib.request
import urllib.parse
import json
from datetime import datetime
from typing import Any

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, TorrentCategory
from ...util.decorator import log_time


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

    @property
    def short_name(self) -> str:
        return "Jackett"

    @property
    def full_name(self) -> str:
        return "Jackett"

    @log_time
    def _search_impl(self, query: str) -> list[SearchResultDTO]:
        """Search Jackett for torrents across all indexers.

        Args:
            query: Search term

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If API request fails or not configured
        """
        if self._config_error:
            raise Exception(self._config_error)

        if not query or not query.strip():
            return []

        url = self._build_search_url(query)
        data = self._fetch_results(url)
        return self._process_results(data)

    def _build_search_url(self, query: str) -> str:
        """Build Jackett API search URL.

        Args:
            query: Search term

        Returns:
            Complete URL with parameters
        """
        base_url = self.jackett_url.rstrip('/')
        endpoint = f"{base_url}/api/v2.0/indexers/all/results"
        params = {
            'apikey': self.api_key,
            'Query': query.strip(),
        }
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
            with urllib.request.urlopen(url, timeout=15) as response:
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
            info_hash = result.get('InfoHash', '')
            if not info_hash:
                return None

            return SearchResultDTO(
                title=result.get('Title', 'Unknown'),
                category=self._map_jackett_category(result),
                seeders=int(result.get('Seeders', 0)),
                leechers=int(result.get('Peers', 0)),
                size=int(result.get('Size', 0)),
                files_count=self._get_files_count(result),
                magnet_link=self._get_magnet_link(result, info_hash),
                info_hash=info_hash,
                upload_date=self._parse_upload_date(result),
                provider=self._build_provider_name(result),
                provider_id=self.id(),
                page_url=self._get_page_url(result),
                fields=self._build_fields(result)
            )
        except (KeyError, ValueError, TypeError):
            return None

    def _get_magnet_link(self,
                         result: dict[str, Any],
                         info_hash: str) -> str:
        """Get magnet link from result, with fallbacks.

        Args:
            result: Result dict from Jackett API
            info_hash: Torrent info hash

        Returns:
            Magnet URI or HTTP(S) torrent file URL
        """
        magnet_link = result.get('MagnetUri', '').strip()
        if magnet_link:
            return magnet_link

        link = result.get('Link', '').strip()
        if link:
            return link

        # Build magnet from info hash as fallback
        return self._build_magnet_link(
            info_hash=info_hash,
            name=result.get('Title', 'Unknown')
        )

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
        """Build provider name in format 'Jackett(IndexerName)'.

        Args:
            result: Result dict from Jackett API

        Returns:
            Provider name string
        """
        tracker_id = result.get('TrackerId', 'Unknown')
        tracker = result.get('Tracker', tracker_id)
        return f"Jackett({tracker})"

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

        Args:
            result: Result dict from Jackett API

        Returns:
            Dictionary of provider-specific fields
        """
        fields = {}
        if result.get('CategoryDesc'):
            fields['category_desc'] = result['CategoryDesc']
        if result.get('Grabs') is not None:
            fields['grabs'] = str(result['Grabs'])
        if result.get('Comments'):
            fields['comments'] = result['Comments']
        return fields

    def _map_jackett_category(self,
                              result: dict[str, Any]) -> TorrentCategory:
        """Map Jackett category to TorrentCategory enum.

        Jackett uses Torznab category IDs:
        - 1000-1999: Console (games)
        - 2000-2999: Movies (video)
        - 3000-3999: Audio
        - 4000-4999: PC (games/software)
        - 5000-5999: TV (video)
        - 6000-6999: XXX
        - 7000-7999: Books (other)

        Args:
            result: Result dict from Jackett API

        Returns:
            TorrentCategory enum value
        """
        category_codes = result.get('Category', [])
        if not category_codes:
            return TorrentCategory.UNKNOWN

        code = self._get_first_category_code(category_codes)
        if code is None:
            return TorrentCategory.UNKNOWN

        return self._get_category_from_code(code, result)

    def _get_first_category_code(
            self,
            category_codes: Any) -> int | None:
        """Extract first category code from codes list/value.

        Args:
            category_codes: Category codes (list or single value)

        Returns:
            First category code as integer or None
        """
        try:
            if isinstance(category_codes, list) and category_codes:
                return int(category_codes[0])
            return int(category_codes)
        except (ValueError, TypeError):
            return None

    def _get_category_from_code(self,
                                code: int,
                                result: dict[str, Any]) -> TorrentCategory:
        """Map Torznab category code to TorrentCategory enum.

        Args:
            code: Torznab category code
            result: Result dict for additional context

        Returns:
            TorrentCategory enum value
        """
        if 1000 <= code < 2000:
            return TorrentCategory.GAMES
        elif 2000 <= code < 3000:
            return TorrentCategory.VIDEO
        elif 3000 <= code < 4000:
            return TorrentCategory.AUDIO
        elif 4000 <= code < 5000:
            # PC can be games or software
            categories = result.get('CategoryDesc', '').lower()
            if any(x in categories for x in ['game', 'games']):
                return TorrentCategory.GAMES
            return TorrentCategory.SOFTWARE
        elif 5000 <= code < 6000:
            return TorrentCategory.VIDEO
        elif 6000 <= code < 7000:
            return TorrentCategory.XXX
        elif 7000 <= code < 8000:
            return TorrentCategory.OTHER

        return TorrentCategory.UNKNOWN

    def details_extended(self, result: SearchResultDTO) -> str:
        """Generate Jackett-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with Jackett details
        """
        if not result.fields:
            return ""

        md = "## Indexer Info\n"

        if 'category_desc' in result.fields:
            md += f"- **Category:** {result.fields['category_desc']}\n"

        if 'grabs' in result.fields:
            md += f"- **Grabs:** {result.fields['grabs']}\n"

        return md
