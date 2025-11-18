"""YTS.mx torrent search provider implementation."""

import urllib.request
import urllib.parse
import json
from datetime import datetime
from typing import Any

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, TorrentCategory
from ...util.decorator import log_time


class YTSProvider(BaseSearchProvider):
    """Search provider for YTS.mx (movie torrents).

    YTS.mx provides a public API for searching movie torrents.
    Documentation: https://yts.mx/api
    """

    API_URL = "https://yts.mx/api/v2/list_movies.json"

    # Recommended trackers from YTS.mx documentation
    TRACKERS = [
        "udp://open.demonii.com:1337/announce",
        "udp://tracker.openbittorrent.com:80",
        "udp://tracker.coppersurfer.tk:6969",
        "udp://glotorrents.pw:6969/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://torrent.gresille.org:80/announce",
        "udp://p4p.arenabg.com:1337",
        "udp://tracker.leechers-paradise.org:6969",
    ]

    @property
    def name(self) -> str:
        return "yts"

    @property
    def display_name(self) -> str:
        return "YTS"

    @log_time
    def _search_impl(self, query: str) -> list[SearchResultDTO]:
        """Search YTS.mx for movie torrents.

        Args:
            query: Movie name to search for
            limit: Maximum number of results

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If API request fails
        """
        if not query or not query.strip():
            return []

        params = {
            'query_term': query.strip(),
            'limit': 50,  # YTS max is 50
            'sort_by': 'seeds',
            'order_by': 'desc'
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get('status') != 'ok':
                raise Exception(f"API error: {data.get('status_message')}")

            movies = data.get('data', {}).get('movies', [])
            if not movies:
                return []

            results = []
            for movie in movies:
                # YTS returns multiple torrents per movie (different qualities)
                torrents = movie.get('torrents', [])
                for torrent in torrents:
                    result = self._parse_torrent(movie, torrent)
                    if result:
                        results.append(result)

            return results

        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

    def _parse_torrent(self, movie: dict[str, Any],
                       torrent: dict[str, Any]) -> SearchResultDTO | None:
        """Parse a single torrent from YTS API response."""
        try:
            info_hash = torrent.get('hash', '')
            if not info_hash:
                return None

            # Build title with quality, year and language
            title = movie.get('title', '')
            year = movie.get('year', '')
            language = movie.get('language', '').upper()
            quality = torrent.get('quality', '')
            full_title = f"{title} ({year})"
            if quality:
                full_title += f" [{quality}]"
            if language:
                full_title += f" [{language}]"

            size = torrent.get('size_bytes', 0)

            magnet_link = self._build_magnet_link(
                info_hash=info_hash,
                name=full_title,
                trackers=self.TRACKERS
            )

            # Parse upload date from unix timestamp
            upload_date = None
            date_uploaded_unix = torrent.get('date_uploaded_unix')
            if date_uploaded_unix:
                upload_date = datetime.fromtimestamp(date_uploaded_unix)

            return SearchResultDTO(
                title=full_title,
                category=TorrentCategory.VIDEO,
                seeders=torrent.get('seeds', 0),
                leechers=torrent.get('peers', 0),
                size=size,
                files_count=None,
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=upload_date,
                provider=self.display_name
            )

        except (KeyError, ValueError, TypeError):
            return None
