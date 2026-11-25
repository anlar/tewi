"""nekoBT torrent search provider implementation."""

import json
import re
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...ui.util import print_size
from ...util.log import get_logger, log_time
from ...util.misc import parse_count
from ..base import BaseSearchProvider
from ..models import (
    Category,
    DetailsLink,
    DetailsSection,
    SearchResult,
    StandardCategories,
)
from ..util import build_magnet_link, read_response

logger = get_logger()


class NekoBtProvider(BaseSearchProvider):
    """Search provider for nekoBT (anime torrents).

    Uses public JSON API, which doesn't require API key for search.
    API documentation: https://wiki.nekobt.to/technical-details/json/
    """

    API_URL = "https://nekobt.to/api/v1"
    SITE_URL = "https://nekobt.to"

    # Max number of results (API allows up to 100)
    RESULTS_LIMIT = 100

    # Max number of files listed in details
    MAX_DETAILS_FILES = 100

    # Media ID prefix mapping to StandardCategories ("s" - series,
    # "m" - movie); torrent category isn't used by nekoBT
    CATEGORY_MAP = {
        "s": StandardCategories.TV_ANIME,
        "m": StandardCategories.MOVIES,
    }

    _MEDIA_ID_RE = re.compile(r"([sm])\d+")
    _TORRENT_ID_RE = re.compile(r"\d+")
    _IMDB_RE = re.compile(r"tt\d+")

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

        # API has no movies/series filter, so results are filtered locally
        parents = {(c.parent or c) for c in categories or []}
        supported = {(c.parent or c) for c in self.CATEGORY_MAP.values()}
        if parents and not parents & supported:
            return []

        # Movies are rarely among the most seeded torrents, so for movies
        # only search relevance order is used to get them in results
        movies_only = parents == {StandardCategories.MOVIES}
        params = {
            "query": query.strip(),
            "limit": self.RESULTS_LIMIT,
            "sort_by": "best" if movies_only else "seeders",
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

        results = []
        for torrent in (data.get("data") or {}).get("results") or []:
            result = self._parse_torrent(torrent)
            if not result:
                continue
            if parents and not any(
                (c.parent or c) in parents for c in result.categories or []
            ):
                continue
            results.append(result)
        return results

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if not result.fields:
            return []

        info: list[tuple[str, str | DetailsLink]] = [
            (label, result.fields[key])
            for key, label in (
                ("audio", "Audio"),
                ("subtitles", "Subtitles"),
                ("uploader", "Uploader"),
                ("groups", "Groups"),
            )
            if key in result.fields
        ]

        if result.fields.get("batch"):
            info.append(("Batch", "Yes"))

        torrent = self._fetch_json("torrents", result.fields.get("torrent_id"))
        media = self._fetch_json("media", result.fields.get("media_id"))

        sections = [DetailsSection("Information", fields=info)]
        sections += self._format_links(result, torrent, media)
        if torrent:
            sections += self._format_files(torrent.get("files"))

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
        imdb = media.get("imdbId")
        if isinstance(imdb, str) and self._IMDB_RE.fullmatch(imdb):
            links.append(("IMDB", f"https://www.imdb.com/title/{imdb}/"))

        if not links:
            return []
        return [
            DetailsSection(
                "Links",
                fields=[(name, DetailsLink(url)) for name, url in links],
            )
        ]

    def _format_files(self, files: Any) -> list[DetailsSection]:
        """Format files section, limited to MAX_DETAILS_FILES entries."""
        if not files or not isinstance(files, list):
            return []

        items = []
        for f in files[: self.MAX_DETAILS_FILES]:
            if not isinstance(f, dict):
                continue
            path = f.get("path") or f.get("name")
            if not path:
                continue
            item = str(path)
            if isinstance(f.get("length"), int):
                item += f" ({print_size(f['length'])})"
            items.append(item)

        if len(files) > self.MAX_DETAILS_FILES:
            more = len(files) - self.MAX_DETAILS_FILES
            items.append(f"...and {more} more")
        return [DetailsSection(f"Files ({len(files)})", items=items)]

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse torrent from search results."""
        try:
            title = torrent.get("title")
            info_hash = torrent.get("infohash")
            tid = str(torrent.get("id") or "")
            if not title or not info_hash:
                return None
            if not self._TORRENT_ID_RE.fullmatch(tid):
                return None
            if torrent.get("deleted") or torrent.get("hidden"):
                return None

            fields = self._build_fields(torrent)
            fields["torrent_id"] = tid

            category = None
            media_id = torrent.get("media_id")
            media_match = self._MEDIA_ID_RE.fullmatch(str(media_id or ""))
            if media_match:
                fields["media_id"] = media_id
                category = self.CATEGORY_MAP[media_match.group(1)]

            upload_date = None
            if isinstance(torrent.get("uploaded_at"), int):
                upload_date = datetime.fromtimestamp(
                    torrent["uploaded_at"] / 1000
                )

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=self._magnet_link(torrent, info_hash, title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=[category] if category else None,
                seeders=parse_count(torrent.get("seeders")),
                leechers=parse_count(torrent.get("leechers")),
                downloads=parse_count(torrent.get("completed")),
                size=parse_count(torrent.get("filesize")),
                files_count=None,
                upload_date=upload_date,
                page_url=f"{self.SITE_URL}/torrents/{tid}",
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (AttributeError, KeyError, ValueError, TypeError):
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

    def _magnet_link(
        self, torrent: dict[str, Any], info_hash: str, title: str
    ) -> str:
        """Use magnet link from API (it has trackers) if it's for torrent."""
        magnet = torrent.get("magnet")
        prefix = f"magnet:?xt=urn:btih:{info_hash}".lower()
        if isinstance(magnet, str) and magnet.lower().startswith(prefix):
            return magnet
        return build_magnet_link(info_hash=info_hash, name=title)

    def _error_message(self, error: urllib.error.HTTPError) -> str:
        """Get error message from API error response."""
        try:
            message = json.loads(error.read().decode("utf-8")).get("message")
        except (OSError, ValueError, AttributeError):
            message = None
        return f"HTTP {error.code}: {message or error.reason}"

    def _is_movie(self, result: SearchResult) -> bool:
        return StandardCategories.MOVIES in (result.categories or [])

    def _langs(self, value: Any) -> list[str]:
        """Split comma-separated languages."""
        if not value or not isinstance(value, str):
            return []
        return [lang.strip() for lang in value.split(",") if lang.strip()]

    def _id(self, value: Any) -> str | None:
        """Validate numeric ID of external site."""
        value = str(value) if isinstance(value, int | str) else ""
        return value if value.isdigit() else None
