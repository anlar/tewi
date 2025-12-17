"""YTS torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...util.log import log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult, StandardCategories
from ..util import (
    build_magnet_link,
    urlopen,
)


class YTSProvider(BaseSearchProvider):
    """Search provider for YTS (movie torrents).

    YTS provides a public API for searching movie torrents.
    Documentation: https://yts.lt/api
    Status: https://yifystatus.com/
    Domains: https://gosites.org/yts
    """

    DOMAIN = "yts.lt"
    API_URL = f"https://{DOMAIN}/api/v2/list_movies.json"

    # Recommended trackers from YTS documentation
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
    def id(self) -> str:
        return "yts"

    @property
    def name(self) -> str:
        return "YTS"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search YTS for movie torrents.

        Args:
            query: Movie name to search for
            categories: Category IDs to filter by - if provided and
                       doesn't contain Movies category, returns empty list
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails
        """
        if not query or not query.strip():
            return []

        # YTS only returns movies - if categories specified and don't
        # include Movies, return empty
        if not self._has_movies_category(categories):
            return []

        data = self._fetch_api_data(query)

        if data.get("status") != "ok":
            raise Exception(f"API error: {data.get('status_message')}")

        movies = data.get("data", {}).get("movies", [])
        if not movies:
            return []

        return self._process_movies(movies)

    def details_extended(self, result: SearchResult) -> str:
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

    def _has_movies_category(self, categories: list[Category] | None) -> bool:
        """Check if categories list includes Movies category.

        Args:
            categories: List of Category objects

        Returns:
            True if categories is None or includes Movies (2000-2999),
            False otherwise
        """
        if not categories:
            return True

        # Check if any category is Movies or Movies subcategory
        for category in categories:
            # Any Movies (sub)category (2xxx)
            if (
                StandardCategories.MOVIES.id <= category.id
                or category.id < StandardCategories.AUDIO.id
            ):
                return True

        return False

    def _fetch_api_data(self, query: str) -> dict:
        """Fetch data from YTS API.

        Args:
            query: Search term

        Returns:
            Parsed JSON response

        Raises:
            Exception: If API request fails
        """
        params = {
            "query_term": query.strip(),
            "limit": 50,  # YTS max is 50
            "sort_by": "seeds",
            "order_by": "desc",
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urlopen(url) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

    def _process_movies(self, movies: list) -> list[SearchResult]:
        """Process movies list into SearchResult objects.

        Args:
            movies: List of movie dicts from API

        Returns:
            List of SearchResult objects
        """
        results = []
        for movie in movies:
            # YTS returns multiple torrents per movie (different qualities)
            torrents = movie.get("torrents", [])
            for torrent in torrents:
                result = self._parse_torrent(movie, torrent)
                if result:
                    results.append(result)
        return results

    def _parse_torrent(
        self, movie: dict[str, Any], torrent: dict[str, Any]
    ) -> SearchResult | None:
        """Parse a single torrent from YTS API response."""
        try:
            # Build title with quality, year and language
            title = movie.get("title")
            year = movie.get("year")
            language = movie.get("language")
            quality = torrent.get("quality")

            full_title = f"{title} ({year})"
            if quality:
                full_title += f" [{quality}]"
            if language:
                full_title += f" [{language.upper()}]"

            info_hash = torrent.get("hash")
            if not info_hash:
                return None

            magnet_link = build_magnet_link(
                info_hash=info_hash, name=full_title, trackers=self.TRACKERS
            )

            # Parse upload date from unix timestamp
            upload_date = None
            date_uploaded_unix = torrent.get("date_uploaded_unix")
            if date_uploaded_unix:
                upload_date = datetime.fromtimestamp(date_uploaded_unix)

            # Construct page URL from movie URL or ID
            page_url = movie.get("url")
            if page_url:
                # Strip query parameters if present
                page_url = page_url.split("?")[0]
            elif movie.get("id"):
                page_url = f"https://{self.DOMAIN}/movies/{movie['id']}"

            # Build provider-specific fields
            fields = self._build_movie_fields(
                movie, torrent, year, language, quality
            )
            fields.update(
                self._build_quality_fields(
                    movie, torrent, year, language, quality
                )
            )

            return SearchResult(
                title=full_title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=torrent.get("url"),
                provider=self.name,
                provider_id=self.id,
                categories=self._get_category_from_quality(quality),
                seeders=torrent.get("seeds"),
                leechers=torrent.get("peers"),
                downloads=None,
                size=torrent.get("size_bytes"),
                files_count=None,
                upload_date=upload_date,
                page_url=page_url,
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _get_category_from_quality(self, quality: str) -> list[Category]:
        """Map YTS quality to Standard category.

        Based on Jackett YTS category mappings:
        - 720p → Movies/HD
        - 1080p → Movies/HD
        - 2160p → Movies/UHD
        - 3D → Movies/3D
        - default → Movies

        Args:
            quality: Quality string from YTS API (e.g., "720p", "1080p")

        Returns:
            List containing the appropriate Standard category
        """
        quality_lower = quality.lower() if quality else ""

        if "2160p" in quality_lower or "4k" in quality_lower:
            return [StandardCategories.MOVIES_UHD]
        elif "3d" in quality_lower:
            return [StandardCategories.MOVIES_3D]
        elif "720p" in quality_lower or "1080p" in quality_lower:
            return [StandardCategories.MOVIES_HD]
        else:
            # Default to general Movies category
            return [StandardCategories.MOVIES]

    def _build_movie_fields(
        self,
        movie: dict[str, Any],
        torrent: dict[str, Any],
        year: str,
        language: str,
        quality: str,
    ) -> dict[str, str]:
        """Build provider-specific fields dictionary.

        Args:
            movie: Movie data from API
            torrent: Torrent data from API
            year: Movie year
            language: Movie language
            quality: Torrent quality

        Returns:
            Dictionary of provider-specific fields
        """
        fields = {}
        if movie.get("rating"):
            fields["rating"] = str(movie["rating"])
        if movie.get("runtime"):
            fields["runtime"] = f"{movie['runtime']} min"
        if movie.get("genres"):
            fields["genres"] = ", ".join(movie["genres"])
        if year:
            fields["year"] = str(year)
        if language:
            fields["language"] = language
        if quality:
            fields["quality"] = quality
        if movie.get("imdb_code"):
            fields["imdb_code"] = movie["imdb_code"]
        if movie.get("summary"):
            fields["summary"] = movie["summary"]
        if movie.get("yt_trailer_code"):
            fields["yt_trailer_code"] = movie["yt_trailer_code"]

        return fields

    def _build_quality_fields(
        self,
        movie: dict[str, Any],
        torrent: dict[str, Any],
        year: str,
        language: str,
        quality: str,
    ) -> dict[str, str]:
        """Build provider-specific fields dictionary.

        Args:
            movie: Movie data from API
            torrent: Torrent data from API
            year: Movie year
            language: Movie language
            quality: Torrent quality

        Returns:
            Dictionary of provider-specific fields
        """
        fields = {}

        if torrent.get("video_codec"):
            fields["video_codec"] = torrent["video_codec"]
        if torrent.get("audio_channels"):
            fields["audio_channels"] = torrent["audio_channels"]
        if torrent.get("type"):
            fields["type"] = torrent["type"]
        if torrent.get("is_repack"):
            fields["is_repack"] = "Yes" if int(torrent["is_repack"]) else "No"
        if torrent.get("bit_depth"):
            fields["bit_depth"] = torrent["bit_depth"]

        return fields

    def _add_movie_info(self, md: str, fields: dict[str, str]) -> str:
        """Add movie information section to markdown."""
        md += "## Movie\n"
        field_mappings = [
            ("year", "Year", None),
            ("runtime", "Runtime", None),
            ("genres", "Genres", None),
            ("language", "Language", None),
            ("rating", "Rating", lambda v: f"{v}/10"),
            ("summary", "Summary", None),
            ("imdb_code", "IMDB", lambda v: f"https://www.imdb.com/title/{v}"),
            (
                "yt_trailer_code",
                "Trailer",
                lambda v: f"https://www.youtube.com/watch?v={v}",
            ),
        ]
        for key, label, formatter in field_mappings:
            if key in fields:
                value = formatter(fields[key]) if formatter else fields[key]
                md += f"- **{label}:** {value}\n"
        return md

    def _add_quality_info(self, md: str, fields: dict[str, str]) -> str:
        """Add quality information section to markdown."""
        md += "## Quality\n"
        field_mappings = [
            ("type", "Type"),
            ("quality", "Quality"),
            ("video_codec", "Video Codec"),
            ("bit_depth", "Bit Depth"),
            ("audio_channels", "Audio Channels"),
            ("is_repack", "Repack"),
        ]
        for key, label in field_mappings:
            if key in fields:
                md += f"- **{label}:** {fields[key]}\n"

        return md
