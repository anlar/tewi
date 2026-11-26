# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""YTS torrent search provider implementation."""

import json
import re
import urllib.error
import urllib.parse
from typing import Any

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import (
    Category,
    DetailsLink,
    DetailsSection,
    SearchResult,
    StandardCategories,
)
from ..util import build_magnet_link, imdb_link, parse_timestamp, read_response

logger = get_logger()


class YTSProvider(BaseSearchProvider):
    """Search provider for YTS (movie torrents).

    YTS provides a public API for searching movie torrents.
    Documentation: https://yts.pw/api
    Status/proxies:
    * https://yifystatus.com/
    * https://ytsproxies.com/
    * https://gosites.org/yts
    """

    DOMAIN = "yts.pw"
    API_URL = "https://movies-api.accel.li/api/v2/list_movies.json"

    # API returns up to 50 movies per page, each with several torrents
    LIMIT = 50

    # Recommended trackers from YTS documentation
    TRACKERS = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.dler.org:6969/announce",
        "udp://open.stealth.si:80/announce",
        "udp://open.demonii.com:1337/announce",
        "https://tracker.moeblog.cn:443/announce",
        "udp://open.dstud.io:6969/announce",
        "udp://tracker.srv00.com:6969/announce",
        "https://tracker.zhuqiy.com:443/announce",
        "https://tracker.pmman.tech:443/announce",
    ]

    # Torrent quality (480p, 720p, 1080p, 1080p.x265, 2160p, 3D) without
    # codec suffix to category, based on Jackett's yts.yml
    CATEGORY_MAP = {
        "480p": StandardCategories.MOVIES_SD,
        "720p": StandardCategories.MOVIES_HD,
        "1080p": StandardCategories.MOVIES_HD,
        "2160p": StandardCategories.MOVIES_UHD,
        "3d": StandardCategories.MOVIES_3D,
    }

    # Torrent source type to display name
    TYPE_NAMES = {"bluray": "BluRay", "web": "WEB"}

    _YOUTUBE_ID_RE = re.compile(r"[\w-]+")

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
            query: Movie title, IMDB ID, or actor/director name
            categories: Categories to filter by - YTS has only movies, so
                search is skipped if Movies isn't selected
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails or response can't be parsed
        """
        query = (query or "").strip()
        if not query:
            return []

        if categories and not any(
            (c.parent or c) == StandardCategories.MOVIES for c in categories
        ):
            return []

        results = []
        for movie in self._fetch_movies(query):
            if not isinstance(movie, dict):
                continue
            # YTS returns several torrents per movie (different qualities)
            torrents = movie.get("torrents") or []
            if not isinstance(torrents, list):
                continue
            for torrent in torrents:
                result = self._parse_torrent(movie, torrent)
                if result:
                    results.append(result)
        return results

    def _fetch_movies(self, query: str) -> list[Any]:
        """Fetch movies matching query from YTS API.

        Args:
            query: Search term

        Returns:
            Movies from API response

        Raises:
            Exception: If API request fails or response can't be parsed
        """
        params = {
            "query_term": query,
            "limit": self.LIMIT,
            "sort_by": "seeds",
            "order_by": "desc",
        }
        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        if not isinstance(data, dict):
            raise Exception("Failed to parse API response: not an object")

        if data.get("status") != "ok":
            raise Exception(f"API error: {data.get('status_message')}")

        # Data has no movies key if nothing is found
        movies = (data.get("data") or {}).get("movies") or []
        if not isinstance(movies, list):
            raise Exception("Failed to parse API response: invalid movies")

        return movies

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate YTS-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Sections with movie details
        """
        if not result.extra:
            return []

        sections = [self._movie_section(result.extra)]
        # Long text is shown as paragraph, not squeezed into field value
        if result.extra.get("summary"):
            sections.append(
                DetailsSection("Summary", text=result.extra["summary"])
            )
        sections.append(self._quality_section(result.extra))
        return sections

    def _parse_torrent(
        self, movie: dict[str, Any], torrent: Any
    ) -> SearchResult | None:
        """Parse a single torrent of a movie from YTS API response."""
        if not isinstance(torrent, dict):
            return None

        try:
            title = movie.get("title")
            if not isinstance(title, str) or not title.strip():
                return None

            info_hash = parse_info_hash(torrent.get("hash"))
            if not info_hash:
                return None

            year = movie.get("year")
            quality = torrent.get("quality")
            source = torrent.get("type")
            language = movie.get("language")

            # Torrents of the same movie differ by quality and source
            full_title = f"{title} ({year})" if year else title
            if quality:
                full_title += f" [{quality}]"
            if source:
                full_title += f" [{self.TYPE_NAMES.get(source, source)}]"
            if language:
                full_title += f" [{language.upper()}]"

            # Remove tracking query parameters, if any
            page_url = (movie.get("url") or "").split("?")[0]
            if not page_url and movie.get("slug"):
                page_url = f"https://{self.DOMAIN}/movies/{movie['slug']}"

            category = self.CATEGORY_MAP.get(
                str(quality or "").lower().split(".")[0],
                StandardCategories.MOVIES,
            )

            return SearchResult(
                title=full_title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(
                    info_hash=info_hash,
                    name=full_title,
                    trackers=self.TRACKERS,
                ),
                torrent_link=torrent.get("url"),
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=(category,),
                seeders=parse_count(torrent.get("seeds")),
                leechers=parse_count(torrent.get("peers")),
                downloads=None,
                size=parse_count(torrent.get("size_bytes")),
                files_count=None,
                upload_date=parse_timestamp(torrent.get("date_uploaded_unix")),
                page_url=page_url or None,
                freeleech=True,  # Public tracker
                extra=self._build_fields(movie, torrent),
            )

        except Exception:
            logger.exception(
                f"YTS: skipping invalid search result {torrent.get('hash')!r}"
            )
            return None

    def _build_fields(
        self, movie: dict[str, Any], torrent: dict[str, Any]
    ) -> dict[str, str]:
        """Build provider-specific fields of a torrent.

        Args:
            movie: Movie data from API
            torrent: Torrent data from API

        Returns:
            Dictionary of non-empty fields, as strings
        """
        fields = {
            "year": movie.get("year"),
            "runtime": movie.get("runtime"),
            "language": movie.get("language"),
            "rating": movie.get("rating"),
            "imdb_code": movie.get("imdb_code"),
            "yt_trailer_code": movie.get("yt_trailer_code"),
            "summary": movie.get("summary"),
            "type": torrent.get("type"),
            "quality": torrent.get("quality"),
            "video_codec": torrent.get("video_codec"),
            "bit_depth": torrent.get("bit_depth"),
            "audio_channels": torrent.get("audio_channels"),
        }
        result = {key: str(value) for key, value in fields.items() if value}

        if result.get("runtime"):
            result["runtime"] += " min"

        genres = movie.get("genres")
        if isinstance(genres, list) and genres:
            result["genres"] = ", ".join(str(g) for g in genres)

        # "0", "1", or empty
        if str(torrent.get("is_repack")) == "1":
            result["is_repack"] = "Yes"

        return result

    def _movie_section(self, fields: dict[str, str]) -> DetailsSection:
        """Build movie information section."""
        field_mappings = [
            ("year", "Year", None),
            ("runtime", "Runtime", None),
            ("genres", "Genres", None),
            ("language", "Language", None),
            ("rating", "Rating", lambda v: f"{v}/10"),
            (
                "imdb_code",
                "IMDB",
                imdb_link,
            ),
            (
                "yt_trailer_code",
                "Trailer",
                lambda v: (
                    DetailsLink(f"https://www.youtube.com/watch?v={v}")
                    if self._YOUTUBE_ID_RE.fullmatch(v)
                    else None
                ),
            ),
        ]
        rows: list[tuple[str, str | DetailsLink]] = []
        for key, label, formatter in field_mappings:
            if key in fields:
                value = formatter(fields[key]) if formatter else fields[key]
                if value:
                    rows.append((label, value))
        return DetailsSection("Movie", fields=tuple(rows))

    def _quality_section(self, fields: dict[str, str]) -> DetailsSection:
        """Build quality information section."""
        field_mappings = [
            ("type", "Type"),
            ("quality", "Quality"),
            ("video_codec", "Video Codec"),
            ("bit_depth", "Bit Depth"),
            ("audio_channels", "Audio Channels"),
            ("is_repack", "Repack"),
        ]
        rows = [
            (label, fields[key])
            for key, label in field_mappings
            if key in fields
        ]
        return DetailsSection("Quality", fields=tuple(rows))
