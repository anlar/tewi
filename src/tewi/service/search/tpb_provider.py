"""The Pirate Bay torrent search provider implementation."""

import urllib.request
import urllib.parse
import json
from datetime import datetime
from typing import Any

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, TorrentCategory
from ...util.decorator import log_time


class TPBProvider(BaseSearchProvider):
    """Search provider for The Pirate Bay (via apibay.org)."""

    API_URL = "https://apibay.org/q.php"

    @property
    def name(self) -> str:
        return "tpb"

    @property
    def display_name(self) -> str:
        return "TPB"

    @log_time
    def _search_impl(self, query: str) -> list[SearchResultDTO]:
        """Search The Pirate Bay for torrents.

        Args:
            query: Search term

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If API request fails
        """
        if not query or not query.strip():
            return []

        params = {
            'q': query.strip(),
            'cat': 0,  # All categories
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # API returns [{"name": "No results returned"}] when no results
            if not data or (len(data) == 1 and
                            data[0].get('name') == 'No results returned'):
                return []

            results = []
            for torrent in data:
                result = self._parse_torrent(torrent)
                if result:
                    results.append(result)

            return results

        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

    def _parse_torrent(self, torrent: dict[str, Any]
                       ) -> SearchResultDTO | None:
        """Parse a single torrent from TPB API response."""
        try:
            info_hash = torrent.get('info_hash', '')
            if not info_hash:
                return None

            name = torrent.get('name', 'Unknown')

            size = int(torrent.get('size', 0))
            category_code = int(torrent.get('category', 0))

            magnet_link = self._build_magnet_link(
                info_hash=info_hash,
                name=name
            )

            # Parse upload date from unix timestamp
            upload_date = None
            added = torrent.get('added')
            if added:
                upload_date = datetime.fromtimestamp(int(added))

            return SearchResultDTO(
                title=name,
                category=self._get_category(category_code),
                seeders=int(torrent.get('seeders', 0)),
                leechers=int(torrent.get('leechers', 0)),
                size=size,
                files_count=int(torrent.get('num_files', None)),
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=upload_date,
                provider=self.display_name
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _get_category(self, code: str) -> TorrentCategory:
        c = code // 100

        match c:
            case 1:
                return TorrentCategory.AUDIO
            case 2:
                return TorrentCategory.VIDEO
            case 3:
                return TorrentCategory.SOFTWARE
            case 4:
                return TorrentCategory.GAMES
            case 5:
                return TorrentCategory.XXX
            case 6:
                return TorrentCategory.OTHER
            case _:
                return TorrentCategory.UNKNOWN
