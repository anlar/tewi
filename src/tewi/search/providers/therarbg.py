# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""TheRARBG torrent search provider implementation."""

import json
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from ...util.format import print_size
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
    build_magnet_link,
    local_time,
    matches_query,
    parse_timestamp,
    query_words,
    read_response,
)

logger = get_logger()


class TheRarbgProvider(BaseSearchProvider):
    """Search provider for TheRARBG (general torrents).

    The site has no documented API. Search uses JSON version of the site
    search page, which is sorted and contains leechers, but misses some
    torrents. It's supplemented by search RSS feed, which contains them.

    Both sources filter by single category only (the last one, if several
    are requested), so they are searched for each category separately.
    """

    SITE_URL = "https://therarbg.com"
    SEARCH_URL = "https://therarbg.com/get-posts/"
    RSS_URL = "https://therarbg.com/api/rss/search/"

    # Max number of results requested from each source
    RESULTS_LIMIT = 100

    # Max number of files listed in details
    MAX_DETAILS_FILES = 100

    # Trackers from magnet links on the site (results have info hash only)
    TRACKERS = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.therarbg.to:6969/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://open.demonii.com:1337/announce",
        "udp://explodie.org:6969/announce",
        "https://ht.therarbg.to/announce",
    ]

    # Category mapping from TheRARBG to StandardCategories
    CATEGORY_MAP = {
        "Movies": StandardCategories.MOVIES,
        "TV": StandardCategories.TV,
        "TV shows": StandardCategories.TV,
        "Games": StandardCategories.PC_GAMES,
        "Music": StandardCategories.AUDIO,
        "Apps": StandardCategories.PC,
        "Documentaries": StandardCategories.TV_DOCUMENTARY,
        "Anime": StandardCategories.TV_ANIME,
        "Books": StandardCategories.BOOKS,
        "E-books": StandardCategories.BOOKS_EBOOK,
        "Other": StandardCategories.OTHER,
        "XXX": StandardCategories.XXX,
    }

    # TheRARBG categories containing results of StandardCategories parent
    # (search by TV and Books includes TV shows and E-books)
    PARENT_TO_RARBG_CATEGORIES = {
        StandardCategories.CONSOLE: {"Games"},
        StandardCategories.MOVIES: {"Movies"},
        StandardCategories.AUDIO: {"Music"},
        StandardCategories.PC: {"Apps", "Games"},
        StandardCategories.TV: {"TV", "Documentaries", "Anime"},
        StandardCategories.XXX: {"XXX"},
        StandardCategories.BOOKS: {"Books"},
        StandardCategories.OTHER: {"Other"},
    }

    _SEEDERS_RE = re.compile(r"(\d+) seeders")
    _NON_WORD_RE = re.compile(r"[\W_]+")
    _IMDB_RE = re.compile(r"tt\d+")

    @property
    def id(self) -> str:
        return "therarbg"

    @property
    def name(self) -> str:
        return "TheRARBG"

    @property
    def short_name(self) -> str:
        return "TRBG"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query or not query.strip():
            return []

        query = query.strip()
        # None searches all categories
        rarbg_categories: list[str | None] = [
            *self._convert_categories_to_rarbg(categories)
        ] or [None]

        # JSON results go first, so they are kept for duplicates, as they
        # have leechers
        results: dict[str, SearchResult] = {}
        for category in rarbg_categories:
            self._merge(results, self._search_json(query, category))
        try:
            for category in rarbg_categories:
                self._merge(results, self._search_rss(query, category))
        except Exception as e:
            # RSS only supplements JSON search results
            logger.warning(f"TheRARBG: failed to search RSS: {e}")

        # Search also returns fuzzy matches (e.g. "Exemplar" for "example")
        words = query_words(query)
        return [r for r in results.values() if matches_query(r.title, words)]

    def _merge(
        self, results: dict[str, SearchResult], new: Iterable[SearchResult]
    ) -> None:
        """Add new results by info hash, keeping already added ones."""
        for result in new:
            results.setdefault(result.info_hash, result)

    def _search_json(
        self, query: str, category: str | None
    ) -> list[SearchResult]:
        """Search JSON version of site search page.

        Args:
            query: Search query
            category: TheRARBG category, or None for all

        Returns:
            Parsed search results
        """
        params: dict[str, Any] = {
            "keywords": query,
            "format": "json",
            "order": "-se",
            "page_size": self.RESULTS_LIMIT,
        }
        if category:
            params["category"] = category
        url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        torrents = data.get("results") if isinstance(data, dict) else None
        if not isinstance(torrents, list):
            raise Exception("Failed to parse API response: invalid results")

        return [r for t in torrents if (r := self._parse_torrent(t))]

    def _search_rss(
        self, query: str, category: str | None
    ) -> list[SearchResult]:
        """Search RSS feed.

        Args:
            query: Search query
            category: TheRARBG category, or None for all

        Returns:
            Parsed search results
        """
        params: dict[str, Any] = {"q": query, "limit": self.RESULTS_LIMIT}
        if category:
            params["category"] = category
        url = f"{self.RSS_URL}?{urllib.parse.urlencode(params)}"

        with self.urlopen(url) as response:
            root = ET.fromstring(read_response(response))  # noqa: S314

        items = root.findall("./channel/item")
        return [r for i in items if (r := self._parse_rss_item(i))]

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if not result.extra:
            return []

        info: list[tuple[str, str | DetailsLink]] = []

        if "r_category" in result.extra:
            info.append(("Category", result.extra["r_category"]))

        if "uploader" in result.extra:
            info.append(("Uploader", result.extra["uploader"]))

        if "tags" in result.extra:
            info.append(("Tags", result.extra["tags"]))

        details = self._fetch_details(result.extra.get("torrent_id"))
        if not details:
            return [DetailsSection("Information", fields=tuple(info))]

        info.extend(self._format_details(details))
        return [
            DetailsSection("Information", fields=tuple(info)),
            *self._format_files(details.get("files")),
            *self._format_trackers(details.get("trackers")),
        ]

    @log_time
    def _fetch_details(self, torrent_id: str | None) -> dict[str, Any] | None:
        """Fetch torrent details (files, trackers) from JSON details page.

        Args:
            torrent_id: TheRARBG torrent ID

        Returns:
            Torrent details, or None if they could not be loaded
        """
        if not torrent_id:
            return None

        # Details page accepts any slug
        tid = urllib.parse.quote(str(torrent_id))
        url = f"{self.SITE_URL}/post-detail/{tid}/x/?format=json"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except (OSError, ValueError) as e:
            logger.warning(f"TheRARBG: failed to fetch details: {e}")
            return None

        return data if isinstance(data, dict) else None

    def _format_details(
        self, details: dict[str, Any]
    ) -> list[tuple[str, str | DetailsLink]]:
        """Format information fields from torrent details."""
        fields: list[tuple[str, str | DetailsLink]] = []

        downloads = details.get("downloads")
        if isinstance(downloads, int) and downloads > 0:
            fields.append(("Downloads", str(downloads)))

        language = details.get("language")
        if language and isinstance(language, str):
            fields.append(("Language", language))

        imdb = details.get("imdb")
        if isinstance(imdb, str) and self._IMDB_RE.fullmatch(imdb):
            imdb_url = f"https://www.imdb.com/title/{imdb}/"
            fields.append(("IMDB", DetailsLink(imdb_url)))

        last_checked = self._parse_iso_date(details.get("last_checked"))
        if last_checked:
            checked = last_checked.strftime("%Y-%m-%d %H:%M")
            fields.append(("Last Checked", checked))

        return fields

    def _format_files(self, files: Any) -> list[DetailsSection]:
        """Format files section, limited to MAX_DETAILS_FILES entries."""
        if not files or not isinstance(files, list):
            return []

        items = []
        for f in files[: self.MAX_DETAILS_FILES]:
            if not isinstance(f, dict):
                continue
            path = f.get("full_location") or f.get("name")
            if not path:
                continue
            item = str(path)
            if isinstance(f.get("size"), int):
                item += f" ({print_size(f['size'])})"
            items.append(item)

        if len(files) > self.MAX_DETAILS_FILES:
            more = len(files) - self.MAX_DETAILS_FILES
            items.append(f"...and {more} more")
        return [DetailsSection(f"Files ({len(files)})", items=tuple(items))]

    def _format_trackers(self, trackers: Any) -> list[DetailsSection]:
        """Format trackers section with seeders/leechers reported by them."""
        if not trackers or not isinstance(trackers, list):
            return []

        items = []
        for t in trackers:
            if not isinstance(t, dict) or not t.get("tracker"):
                continue
            item = str(t["tracker"])
            seeders, leechers = t.get("seeders"), t.get("leechers")
            if isinstance(seeders, int) and isinstance(leechers, int):
                item += f" ({seeders} seeders, {leechers} leechers)"
            items.append(item)
        return [DetailsSection("Trackers", items=tuple(items))] if items else []

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse torrent from JSON search results."""
        if not isinstance(torrent, dict):
            return None

        try:
            title = torrent.get("n")
            info_hash = parse_info_hash(torrent.get("h"))
            tid = torrent.get("pk")
            if not title or not info_hash or not tid:
                return None

            fields: dict[str, Any] = {"torrent_id": tid}

            category = torrent.get("c")
            if category:
                fields["r_category"] = category

            uploader = torrent.get("u")
            if uploader:
                fields["uploader"] = uploader

            tags = torrent.get("tg")
            if tags and isinstance(tags, list):
                fields["tags"] = ", ".join(str(t) for t in tags)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=self._magnet_link(info_hash, title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=self._get_categories(category),
                seeders=parse_count(torrent.get("se")),
                leechers=parse_count(torrent.get("le")),
                downloads=None,
                size=parse_count(torrent.get("s")),
                files_count=None,
                upload_date=parse_timestamp(torrent.get("a")),
                page_url=self._page_url(tid, title),
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                f"TheRARBG: skipping invalid search result {torrent.get('h')!r}"
            )
            return None

    def _parse_rss_item(self, item: ET.Element) -> SearchResult | None:
        """Parse torrent from RSS feed item."""
        try:
            title = item.findtext("title")
            info_hash = parse_info_hash(item.findtext("guid"))
            link = item.findtext("link") or ""
            # Link format: https://therarbg.com/post-detail/<id>/<slug>/
            match = re.search(r"/post-detail/([^/]+)/", link)
            if not title or not info_hash or not match:
                return None
            tid = match.group(1)

            fields: dict[str, Any] = {"torrent_id": tid}

            category = item.findtext("category")
            if category:
                fields["r_category"] = category

            seeders = None
            seeders_match = self._SEEDERS_RE.search(
                item.findtext("description") or ""
            )
            if seeders_match:
                seeders = int(seeders_match.group(1))

            enclosure = item.find("enclosure")
            size = parse_count(
                enclosure.get("length") if enclosure is not None else None
            )

            upload_date = None
            pub_date = item.findtext("pubDate")
            if pub_date:
                upload_date = parsedate_to_datetime(pub_date)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=self._magnet_link(info_hash, title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=self._get_categories(category),
                seeders=seeders,
                # Feed has no leechers
                leechers=None,
                downloads=None,
                size=size,
                files_count=None,
                upload_date=local_time(upload_date),
                page_url=self._page_url(tid, title),
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                f"TheRARBG: skipping invalid RSS item {item.findtext('guid')!r}"
            )
            return None

    def _magnet_link(self, info_hash: str, title: str) -> str:
        """Build magnet link with site trackers."""
        return build_magnet_link(
            info_hash=info_hash, name=title, trackers=self.TRACKERS
        )

    def _page_url(self, tid: str, title: str) -> str:
        """Build torrent page URL."""
        slug = self._NON_WORD_RE.sub("-", title.lower()).strip("-") or "x"
        tid = urllib.parse.quote(str(tid))
        return f"{self.SITE_URL}/post-detail/{tid}/{urllib.parse.quote(slug)}/"

    def _parse_iso_date(self, value: Any) -> datetime | None:
        """Parse ISO 8601 date string returned by API."""
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _get_categories(self, category: Any) -> tuple[Category, ...]:
        """Map TheRARBG category name to StandardCategories."""
        mapped = self.CATEGORY_MAP.get(category)
        return (mapped,) if mapped else ()

    def _convert_categories_to_rarbg(
        self, categories: list[Category] | None
    ) -> list[str]:
        """Convert StandardCategories to TheRARBG categories to search.

        Args:
            categories: Selected categories

        Returns:
            Sorted TheRARBG categories, or empty list to search all
            categories
        """
        if not categories:
            return []

        rarbg_categories: set[str] = set()
        for category in categories:
            parent = category.parent or category
            rarbg_categories |= self.PARENT_TO_RARBG_CATEGORIES.get(
                parent, set()
            )
        return sorted(rarbg_categories)
