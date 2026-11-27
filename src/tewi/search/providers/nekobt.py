# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""nekoBT torrent search provider implementation."""

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
from ..util import (
    format_files,
    imdb_link,
    parse_timestamp,
    provider_magnet_link,
    read_response,
)

logger = get_logger()


class NekoBtProvider(BaseSearchProvider):
    """Search provider for nekoBT (anime torrents).

    Uses public JSON API, which doesn't require API key for search.
    API documentation: https://wiki.nekobt.to/technical-details/json/
    """

    # Torrent and media details are downloaded from API
    remote_details = True

    API_URL = "https://nekobt.to/api/v1"
    SITE_URL = "https://nekobt.to"

    # Max number of results (API allows up to 100)
    RESULTS_LIMIT = 100

    # Media ID prefix mapping to StandardCategories ("s" - series,
    # "m" - movie); torrent category isn't used by nekoBT. Torrents without
    # media are anime, as in nekoBT Torznab API.
    CATEGORY_MAP = {
        "s": StandardCategories.TV_ANIME,
        "m": StandardCategories.MOVIES,
    }

    _MEDIA_ID_RE = re.compile(r"([sm])\d+")
    _TORRENT_ID_RE = re.compile(r"\d+")

    @property
    def id(self) -> str:
        return "nekobt"

    @property
    def name(self) -> str:
        return "nekoBT"

    @property
    def short_name(self) -> str:
        return "NEKO"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query or not query.strip():
            return []

        # API has no movies/series filter, results are filtered by search
        # manager
        parents = {(c.parent or c) for c in categories or []}
        supported = {(c.parent or c) for c in self.CATEGORY_MAP.values()}
        if parents and not parents & supported:
            return []

        # Movies are rarely among the most seeded torrents, so for movies
        # only search relevance order is used to get them in results
        movies_only = parents == {StandardCategories.MOVIES}
        torrents = self._fetch_torrents(
            query.strip(), "best" if movies_only else "seeders"
        )
        return [r for t in torrents if (r := self._parse_torrent(t))]

    def _fetch_torrents(self, query: str, sort_by: str) -> list[Any]:
        """Fetch torrents matching query from search API.

        Args:
            query: Search term
            sort_by: Sort order

        Returns:
            Torrents from API response

        Raises:
            Exception: If API request fails or response can't be parsed
        """
        params = {
            "query": query,
            "limit": self.RESULTS_LIMIT,
            "sort_by": sort_by,
        }
        query_string = urllib.parse.urlencode(params)
        url = f"{self.API_URL}/torrents/search?{query_string}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise Exception(f"API error: {self._error_message(e)}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        if not isinstance(data, dict) or data.get("error"):
            message = data.get("message") if isinstance(data, dict) else None
            raise Exception(f"API error: {message or 'unknown error'}")

        torrents = data.get("data")
        if isinstance(torrents, dict):
            torrents = torrents.get("results")
        if not isinstance(torrents, list):
            raise Exception("Failed to parse API response: invalid results")
        return torrents

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        torrent = self._fetch_json("torrents", result.extra.get("torrent_id"))
        media = self._fetch_json("media", result.extra.get("media_id"))
        return self._details_sections(result, torrent, media)

    def details_extended_offline(
        self, result: SearchResult
    ) -> list[DetailsSection] | None:
        details = []
        for kind, key in (("torrents", "torrent_id"), ("media", "media_id")):
            item_id = result.extra.get(key)
            if not item_id:
                details.append(None)
                continue
            cached = self._details_cache.get(f"{kind}/{item_id}")
            if cached is None:
                return None
            details.append(cached)
        return self._details_sections(result, *details)

    def _details_sections(
        self,
        result: SearchResult,
        torrent: dict[str, Any] | None,
        media: dict[str, Any] | None,
    ) -> list[DetailsSection]:
        """Build details sections from result and downloaded details.

        Args:
            result: Search result to format
            torrent: Downloaded torrent details, None if not loaded
            media: Downloaded media details, None if not loaded

        Returns:
            Sections with provider details
        """
        if not result.extra:
            return []

        info: list[tuple[str, str | DetailsLink]] = [
            (label, result.extra[key])
            for key, label in (
                ("audio", "Audio"),
                ("subtitles", "Subtitles"),
                ("uploader", "Uploader"),
                ("groups", "Groups"),
            )
            if key in result.extra
        ]

        if result.extra.get("batch"):
            info.append(("Batch", "Yes"))

        sections = [DetailsSection("Information", fields=tuple(info))]
        sections += self._format_links(result, torrent, media)
        if torrent:
            sections += format_files(
                torrent.get("files"), ("path", "name"), "length"
            )

        return sections

    @log_time
    def _fetch_json(
        self, kind: str, item_id: str | None
    ) -> dict[str, Any] | None:
        """Fetch torrent or media details from JSON API.

        Args:
            kind: API collection ("torrents" or "media")
            item_id: Torrent or media ID

        Returns:
            Details, or None if they could not be loaded
        """
        if not item_id:
            return None
        return self._cached_details(
            f"{kind}/{item_id}", lambda: self._download_json(kind, item_id)
        )

    @log_time
    def _download_json(self, kind: str, item_id: str) -> dict[str, Any] | None:
        """Download torrent or media details, see `_fetch_json`."""
        url = f"{self.API_URL}/{kind}/{urllib.parse.quote(item_id)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except (OSError, ValueError) as e:
            logger.warning(f"nekoBT: failed to fetch {kind} details: {e}")
            return None

        if not isinstance(data, dict) or data.get("error"):
            return None
        details = data.get("data")
        return details if isinstance(details, dict) else None

    def _format_links(
        self,
        result: SearchResult,
        torrent: dict[str, Any] | None,
        media: dict[str, Any] | None,
    ) -> list[DetailsSection]:
        """Format links to AniList (from torrent details), TVDB, TMDB and
        IMDB (from media details) pages."""
        links = []

        anilist = self._id((torrent or {}).get("anilist_id"))
        if anilist:
            links.append(("AniList", f"https://anilist.co/anime/{anilist}"))

        media = media or {}
        tvdb = self._id(media.get("tvdbId"))
        if tvdb:
            links.append(
                ("TVDB", f"https://thetvdb.com/dereferrer/series/{tvdb}")
            )
        tmdb = self._id(media.get("tmdbId"))
        if tmdb:
            kind = "movie" if self._is_movie(result) else "tv"
            links.append(("TMDB", f"https://www.themoviedb.org/{kind}/{tmdb}"))
        imdb = imdb_link(media.get("imdbId"))
        if imdb:
            links.append(("IMDB", imdb.url))

        if not links:
            return []
        return [
            DetailsSection(
                "Links",
                fields=tuple((name, DetailsLink(url)) for name, url in links),
            )
        ]

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse torrent from search results."""
        if not isinstance(torrent, dict):
            return None

        try:
            title = torrent.get("title")
            info_hash = parse_info_hash(torrent.get("infohash"))
            tid = str(torrent.get("id") or "")
            if not title or not info_hash:
                return None
            if not self._TORRENT_ID_RE.fullmatch(tid):
                return None
            if torrent.get("deleted") or torrent.get("hidden"):
                return None

            fields = self._build_fields(torrent)
            fields["torrent_id"] = tid

            category = StandardCategories.TV_ANIME
            media_id = torrent.get("media_id")
            media_match = self._MEDIA_ID_RE.fullmatch(str(media_id or ""))
            if media_match:
                fields["media_id"] = media_id
                category = self.CATEGORY_MAP[media_match.group(1)]

            # Unix timestamp in milliseconds, as int or digit string
            uploaded_at = parse_count(torrent.get("uploaded_at"))

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=provider_magnet_link(
                    torrent.get("magnet"), info_hash, title
                ),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=(category,),
                seeders=parse_count(torrent.get("seeders")),
                leechers=parse_count(torrent.get("leechers")),
                downloads=parse_count(torrent.get("completed")),
                size=parse_count(torrent.get("filesize")),
                files_count=None,
                upload_date=parse_timestamp(
                    uploaded_at // 1000 if uploaded_at else None
                ),
                page_url=f"{self.SITE_URL}/torrents/{tid}",
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                "nekoBT: skipping invalid search result "
                f"{torrent.get('infohash')!r}"
            )
            return None

    def _build_fields(self, torrent: dict[str, Any]) -> dict[str, Any]:
        """Build provider-specific fields shown in details."""
        fields: dict[str, Any] = {}

        audio = self._langs(torrent.get("audio_lang"))
        if audio:
            fields["audio"] = ", ".join(audio)

        subtitles = self._langs(torrent.get("fsub_lang")) + self._langs(
            torrent.get("sub_lang")
        )
        if subtitles:
            subtitles = list(dict.fromkeys(subtitles))
            fields["subtitles"] = ", ".join(subtitles)

        uploader = torrent.get("uploader")
        if torrent.get("anonymous"):
            fields["uploader"] = "Anonymous"
        elif isinstance(uploader, dict) and uploader.get("display_name"):
            fields["uploader"] = uploader["display_name"]

        groups = torrent.get("groups")
        if isinstance(groups, list):
            names = [
                g["display_name"]
                for g in groups
                if isinstance(g, dict) and g.get("display_name")
            ]
            if names:
                fields["groups"] = ", ".join(names)

        if torrent.get("batch") is True:
            fields["batch"] = True

        return fields

    def _error_message(self, error: urllib.error.HTTPError) -> str:
        """Get error message from API error response."""
        try:
            message = json.loads(error.read().decode("utf-8")).get("message")
        except (OSError, ValueError, AttributeError):
            message = None
        return f"HTTP {error.code}: {message or error.reason}"

    def _is_movie(self, result: SearchResult) -> bool:
        return StandardCategories.MOVIES in result.categories

    def _langs(self, value: Any) -> list[str]:
        """Split comma-separated languages."""
        if not value or not isinstance(value, str):
            return []
        return [lang.strip() for lang in value.split(",") if lang.strip()]

    def _id(self, value: Any) -> str | None:
        """Validate numeric ID of external site."""
        value = str(value) if isinstance(value, int | str) else ""
        return value if value.isdigit() else None
