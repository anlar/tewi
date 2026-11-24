"""TheRARBG torrent search provider implementation."""

import json
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from ...ui.util import print_size
from ...util.log import get_logger, log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult, StandardCategories
from ..util import (
    build_magnet_link,
    escape_markdown,
    matches_query,
    query_words,
    read_response,
)

logger = get_logger()


class TheRarbgProvider(BaseSearchProvider):
    """Search provider for TheRARBG (general torrents).

    The site has no documented API. Search uses JSON version of the site
    search page, which is sorted and contains leechers, but misses some
    torrents. It's supplemented by search RSS feed, which contains them.
    """

    SITE_URL = "https://therarbg.com"
    SEARCH_URL = "https://therarbg.com/get-posts/"
    RSS_URL = "https://therarbg.com/api/rss/search/"

    # Max number of results requested from each source
    RESULTS_LIMIT = 100

    # Max number of files listed in details
    MAX_DETAILS_FILES = 100

    # Category mapping from TheRARBG to StandardCategories
    CATEGORY_MAP = {
        "Movies": StandardCategories.MOVIES,
        "TV": StandardCategories.TV,
        "Games": StandardCategories.PC_GAMES,
        "Music": StandardCategories.AUDIO,
        "Apps": StandardCategories.PC,
        "Documentaries": StandardCategories.TV_DOCUMENTARY,
        "Anime": StandardCategories.TV_ANIME,
        "Books": StandardCategories.BOOKS,
        "Other": StandardCategories.OTHER,
        "XXX": StandardCategories.XXX,
    }

    # TheRARBG categories containing results of StandardCategories parent
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
        rarbg_categories = self._convert_categories_to_rarbg(categories)

        results = self._search_json(query, rarbg_categories)
        try:
            rss_results = self._search_rss(query, rarbg_categories)
        except Exception as e:
            # RSS only supplements JSON search results
            logger.warning(f"TheRARBG: failed to search RSS: {e}")
            rss_results = []

        known = {r.info_hash for r in results}
        results += [r for r in rss_results if r.info_hash not in known]

        # Search also returns fuzzy matches (e.g. "Exemplar" for "example")
        words = query_words(query)
        return [r for r in results if matches_query(r.title, words)]

    def _search_json(
        self, query: str, rarbg_categories: list[str]
    ) -> list[SearchResult]:
        """Search JSON version of site search page.

        Args:
            query: Search query
            rarbg_categories: TheRARBG categories, or empty list for all

        Returns:
            Parsed search results
        """
        params: list[tuple[str, Any]] = [
            ("keywords", query),
            ("format", "json"),
            ("order", "-se"),
            ("page_size", self.RESULTS_LIMIT),
        ]
        params += [("category", c) for c in rarbg_categories]
        url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        if not isinstance(data, dict):
            return []

        results = []
        for torrent in data.get("results") or []:
            result = self._parse_torrent(torrent)
            if result:
                results.append(result)
        return results

    def _search_rss(
        self, query: str, rarbg_categories: list[str]
    ) -> list[SearchResult]:
        """Search RSS feed.

        Feed filters by single category only, so for several categories
        all results are requested and filtered locally.

        Args:
            query: Search query
            rarbg_categories: TheRARBG categories, or empty list for all

        Returns:
            Parsed search results
        """
        params: dict[str, Any] = {"q": query, "limit": self.RESULTS_LIMIT}
        if len(rarbg_categories) == 1:
            params["category"] = rarbg_categories[0]
        url = f"{self.RSS_URL}?{urllib.parse.urlencode(params)}"

        with self.urlopen(url) as response:
            root = ET.fromstring(read_response(response))  # noqa: S314

        results = []
        for item in root.findall("./channel/item"):
            category = item.findtext("category")
            if rarbg_categories and category not in rarbg_categories:
                continue
            result = self._parse_rss_item(item)
            if result:
                results.append(result)
        return results

    def details_extended(self, result: SearchResult) -> str:
        if not result.fields:
            return ""

        md = "## Information\n"

        if "r_category" in result.fields:
            md += f"- **Category:** {result.fields['r_category']}\n"

        if "uploader" in result.fields:
            md += f"- **Uploader:** {result.fields['uploader']}\n"

        if "tags" in result.fields:
            md += f"- **Tags:** {result.fields['tags']}\n"

        details = self._fetch_details(result.fields.get("torrent_id"))
        if details:
            md += self._format_details(details)

        return md

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

    def _format_details(self, details: dict[str, Any]) -> str:
        """Format torrent details as Markdown sections."""
        md = ""

        downloads = details.get("downloads")
        if isinstance(downloads, int) and downloads > 0:
            md += f"- **Downloads:** {downloads}\n"

        language = details.get("language")
        if language and isinstance(language, str):
            md += f"- **Language:** {escape_markdown(language)}\n"

        imdb = details.get("imdb")
        if isinstance(imdb, str) and self._IMDB_RE.fullmatch(imdb):
            md += f"- **IMDB:** https://www.imdb.com/title/{imdb}/\n"

        last_checked = self._parse_iso_date(details.get("last_checked"))
        if last_checked:
            checked = last_checked.strftime("%Y-%m-%d %H:%M")
            md += f"- **Last Checked:** {checked}\n"

        md += self._format_files(details.get("files"))
        md += self._format_trackers(details.get("trackers"))
        return md

    def _format_files(self, files: Any) -> str:
        """Format files section, limited to MAX_DETAILS_FILES entries."""
        if not files or not isinstance(files, list):
            return ""

        md = f"\n## Files ({len(files)})\n"
        for f in files[: self.MAX_DETAILS_FILES]:
            if not isinstance(f, dict):
                continue
            path = f.get("full_location") or f.get("name")
            if not path:
                continue
            md += f"- {escape_markdown(path)}"
            if isinstance(f.get("size"), int):
                md += f" ({print_size(f['size'])})"
            md += "\n"

        if len(files) > self.MAX_DETAILS_FILES:
            more = len(files) - self.MAX_DETAILS_FILES
            md += f"- ...and {more} more\n"
        return md

    def _format_trackers(self, trackers: Any) -> str:
        """Format trackers section with seeders/leechers reported by them."""
        if not trackers or not isinstance(trackers, list):
            return ""

        md = ""
        for t in trackers:
            if not isinstance(t, dict) or not t.get("tracker"):
                continue
            md += f"- {escape_markdown(t['tracker'])}"
            seeders, leechers = t.get("seeders"), t.get("leechers")
            if isinstance(seeders, int) and isinstance(leechers, int):
                md += f" ({seeders} seeders, {leechers} leechers)"
            md += "\n"
        return f"\n## Trackers\n{md}" if md else ""

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse torrent from JSON search results."""
        try:
            title = torrent.get("n")
            info_hash = torrent.get("h")
            tid = torrent.get("pk")
            if not title or not info_hash or not tid:
                return None

            fields: dict[str, Any] = {"torrent_id": tid}

            category = torrent.get("c")
            if category:
                fields["r_category"] = escape_markdown(category)

            uploader = torrent.get("u")
            if uploader:
                fields["uploader"] = escape_markdown(uploader)

            tags = torrent.get("tg")
            if tags and isinstance(tags, list):
                fields["tags"] = ", ".join(escape_markdown(t) for t in tags)

            upload_date = None
            if isinstance(torrent.get("a"), int):
                upload_date = datetime.fromtimestamp(torrent["a"])

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=self._get_categories(category),
                seeders=torrent.get("se"),
                leechers=torrent.get("le"),
                downloads=None,
                size=torrent.get("s"),
                files_count=None,
                upload_date=upload_date,
                page_url=self._page_url(tid, title),
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (AttributeError, KeyError, ValueError, TypeError):
            return None

    def _parse_rss_item(self, item: ET.Element) -> SearchResult | None:
        """Parse torrent from RSS feed item."""
        try:
            title = item.findtext("title")
            info_hash = item.findtext("guid")
            link = item.findtext("link") or ""
            # Link format: https://therarbg.com/post-detail/<id>/<slug>/
            match = re.search(r"/post-detail/([^/]+)/", link)
            if not title or not info_hash or not match:
                return None
            tid = match.group(1)

            fields: dict[str, Any] = {"torrent_id": tid}

            category = item.findtext("category")
            if category:
                fields["r_category"] = escape_markdown(category)

            seeders = None
            seeders_match = self._SEEDERS_RE.search(
                item.findtext("description") or ""
            )
            if seeders_match:
                seeders = int(seeders_match.group(1))

            size = None
            enclosure = item.find("enclosure")
            length = enclosure.get("length") if enclosure is not None else None
            if length and length.isdigit():
                size = int(length)

            upload_date = None
            pub_date = item.findtext("pubDate")
            if pub_date:
                upload_date = parsedate_to_datetime(pub_date)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
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
                upload_date=upload_date,
                page_url=self._page_url(tid, title),
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (AttributeError, KeyError, ValueError, TypeError):
            return None

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

    def _get_categories(self, category: Any) -> list[Category] | None:
        """Map TheRARBG category name to StandardCategories."""
        mapped = self.CATEGORY_MAP.get(category)
        return [mapped] if mapped else None

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
            rarbg_ids = self.PARENT_TO_RARBG_CATEGORIES.get(parent)
            if not rarbg_ids:
                return []
            rarbg_categories |= rarbg_ids

        return sorted(rarbg_categories)
