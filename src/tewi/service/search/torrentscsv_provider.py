"""TorrentsCSV.com torrent search provider implementation."""

import urllib.request
import urllib.parse
import json
from datetime import datetime
from typing import Any

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO


class TorrentsCsvProvider(BaseSearchProvider):
    """Search provider for torrents-csv.com (general torrents).

    TorrentsCSV provides a public API for searching torrent metadata.
    Documentation: https://git.torrents-csv.com/heretic/torrents-csv-server
    """

    API_URL = "https://torrents-csv.com/service/search"

    @property
    def name(self) -> str:
        return "torrentscsv"

    @property
    def display_name(self) -> str:
        return "T-CSV"

    def search(self, query: str) -> list[SearchResultDTO]:
        """Search torrents-csv.com for torrents.

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
            'size': 50,  # Limit results
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            torrents = data.get('torrents', [])
            if not torrents:
                return []

            results = []
            for torrent in torrents:
                result = self._parse_torrent(torrent)
                if result:
                    results.append(result)

            return results

        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

    def _parse_torrent(self, torrent: dict[str, Any]) -> SearchResultDTO | None:
        """Parse a single torrent from TorrentsCSV API response."""
        try:
            info_hash = torrent.get('infohash', '')
            if not info_hash:
                return None

            name = torrent.get('name', 'Unknown')

            size = torrent.get('size_bytes', 0)

            magnet_link = self._build_magnet_link(
                info_hash=info_hash,
                name=name
            )

            # Parse upload date from unix timestamp
            upload_date = None
            created_unix = torrent.get('created_unix')
            if created_unix:
                upload_date = datetime.fromtimestamp(created_unix)

            return SearchResultDTO(
                title=name,
                category=None,
                seeders=torrent.get('seeders', 0),
                leechers=torrent.get('leechers', 0),
                size=size,
                files_count=None,
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=upload_date,
                provider=self.display_name
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _build_magnet_link(self, info_hash: str, name: str) -> str:
        """Build a magnet link from hash and name.

        Args:
            info_hash: Torrent info hash
            name: Display name for the torrent

        Returns:
            Magnet URI string
        """
        encoded_name = urllib.parse.quote(name)

        # TorrentsCSV relies on DHT, no trackers needed
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}"

        return magnet
