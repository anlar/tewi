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

            # Build provider-specific fields
            fields = {}
            if movie.get('rating'):
                fields['rating'] = str(movie['rating'])
            if movie.get('runtime'):
                fields['runtime'] = f"{movie['runtime']} min"
            if movie.get('genres'):
                fields['genres'] = ', '.join(movie['genres'])
            if year:
                fields['year'] = str(year)
            if language:
                fields['language'] = language
            if quality:
                fields['quality'] = quality
            if movie.get('imdb_code'):
                fields['imdb_code'] = movie['imdb_code']
            if torrent.get('video_codec'):
                fields['video_codec'] = torrent['video_codec']
            if torrent.get('audio_channels'):
                fields['audio_channels'] = torrent['audio_channels']

            # Construct page URL from movie URL or ID
            page_url = movie.get('url')
            if not page_url and movie.get('id'):
                page_url = f"https://yts.mx/movies/{movie['id']}"

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
                provider=self.display_name,
                page_url=page_url,
                fields=fields
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _add_movie_info(self, md: str, fields: dict[str, str]) -> str:
        """Add movie information section to markdown."""
        md += "## Movie Information\n"
        field_mappings = [
            ('rating', 'Rating', lambda v: f"{v}/10"),
            ('year', 'Year', None),
            ('runtime', 'Runtime', None),
            ('genres', 'Genres', None),
            ('language', 'Language', None),
        ]
        for key, label, formatter in field_mappings:
            if key in fields:
                value = formatter(fields[key]) if formatter else fields[key]
                md += f"- **{label}:** {value}\n"
        return md

    def _add_quality_info(self, md: str, fields: dict[str, str]) -> str:
        """Add quality information section to markdown."""
        md += "## Quality Information\n"
        field_mappings = [
            ('quality', 'Quality'),
            ('video_codec', 'Video Codec'),
            ('audio_channels', 'Audio'),
        ]
        for key, label in field_mappings:
            if key in fields:
                md += f"- **{label}:** {fields[key]}\n"

        if 'imdb_code' in fields:
            imdb_code = fields['imdb_code']
            imdb_url = f"https://www.imdb.com/title/{imdb_code}/"
            md += f"- **IMDB:** [{imdb_code}]({imdb_url})\n"
        return md

    def details_extended(self, result: SearchResultDTO) -> str:
        """Generate YTS-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with movie details
        """
        if not result.fields:
            return ""

        md = ""
        md = self._add_movie_info(md, result.fields)
        md = self._add_quality_info(md, result.fields)
        return md
