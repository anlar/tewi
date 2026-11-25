"""LimeTorrents torrent search provider implementation."""

import html
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from ...util.log import log_time
from ...util.misc import parse_info_hash
from ..base import BaseSearchProvider
from ..models import Category, DetailsSection, SearchResult, StandardCategories
from ..util import build_magnet_link, matches_query, query_words, read_response


class LimeTorrentsProvider(BaseSearchProvider):
    """Search provider for LimeTorrents (general torrents).

    The site has no API. Search uses search RSS feed, which returns up to
    40 results without sorting or category filtering.
    """

    RSS_URL = "https://www.limetorrents.fun/searchrss/"

    # Top-level category mapping from LimeTorrents to StandardCategories
    CATEGORY_MAP = {
        "Anime": StandardCategories.TV_ANIME,
        "Applications": StandardCategories.PC,
        "Games": StandardCategories.PC_GAMES,
        "Movies": StandardCategories.MOVIES,
        "Music": StandardCategories.AUDIO,
        "Other": StandardCategories.OTHER,
        "TV shows": StandardCategories.TV,
    }

    # Subcategory mapping, for subcategories more specific than category
    SUBCATEGORY_MAP = {
        "Applications - Mac": StandardCategories.PC_MAC,
        "Applications - Handheld": StandardCategories.PC_MOBILE_OTHER,
        "Games - Handheld": StandardCategories.CONSOLE_OTHER,
        "Games - Mac": StandardCategories.PC_MAC,
        "Games - PS2": StandardCategories.CONSOLE_OTHER,
        "Games - Wii": StandardCategories.CONSOLE_WII,
        "Games - XBOX360": StandardCategories.CONSOLE_XBOX360,
        "Music - Music videos": StandardCategories.AUDIO_VIDEO,
        "Other - Audio Books": StandardCategories.AUDIO_AUDIOBOOK,
        "Other - Comics": StandardCategories.BOOKS_COMICS,
        "Other - E-books": StandardCategories.BOOKS_EBOOK,
        # Feed also uses short name
        "E-books": StandardCategories.BOOKS_EBOOK,
    }

    _PEERS_RE = re.compile(r"Seeds:\s*(\d+)\s*,\s*Leechers\s*(\d+)")
    # Info hash is available in .torrent file link only
    _HASH_RE = re.compile(r"/torrent/([0-9A-Fa-f]{40})\.torrent")

    @property
    def id(self) -> str:
        return "limetorrents"

    @property
    def name(self) -> str:
        return "LimeTorrents"

    @property
    def short_name(self) -> str:
        return "LIME"

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
        url = f"{self.RSS_URL}{urllib.parse.quote(query, safe='')}/"

        try:
            with self.urlopen(url) as response:
                data = read_response(response)
            # Feed is followed by unrelated script
            end = data.find(b"</rss>")
            if end >= 0:
                data = data[: end + len(b"</rss>")]
            root = ET.fromstring(data)  # noqa: S314
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except ET.ParseError as e:
            raise Exception(f"Failed to parse RSS feed: {e}")

        # E.g. error page, which shouldn't be shown as no results
        if root.tag != "rss":
            raise Exception(f"Failed to parse RSS feed: unexpected {root.tag}")

        # Feed has no category filter, so results are filtered locally
        parents = {(c.parent or c) for c in categories or []}
        words = query_words(query)

        results = []
        for item in root.findall("./channel/item"):
            result = self._parse_item(item)
            if not result:
                continue
            # Search also returns fuzzy matches (e.g. "Exemplar" for "example")
            if not matches_query(result.title, words):
                continue
            if parents and not self._in_categories(result, parents):
                continue
            results.append(result)
        return results

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if not result.fields:
            return []

        fields = []
        if "l_category" in result.fields:
            fields.append(("Category", result.fields["l_category"]))

        return [DetailsSection("Information", fields=fields)]

    def _parse_item(self, item: ET.Element) -> SearchResult | None:
        """Parse torrent from RSS feed item."""
        try:
            title = item.findtext("title")
            enclosure = item.find("enclosure")
            hash_match = self._HASH_RE.search(
                enclosure.get("url", "") if enclosure is not None else ""
            )
            if not title or not hash_match:
                return None
            # Titles are escaped twice
            title = html.unescape(title)
            info_hash = parse_info_hash(hash_match.group(1))

            seeders, leechers = None, None
            peers_match = self._PEERS_RE.search(
                item.findtext("description") or ""
            )
            if peers_match:
                seeders = int(peers_match.group(1))
                leechers = int(peers_match.group(2))

            size = None
            size_text = item.findtext("size")
            if size_text and size_text.isdigit():
                size = int(size_text)

            fields = {}
            category = item.findtext("category")
            if category:
                fields["l_category"] = category
            mapped = self.get_category(category)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                # .torrent link leads to third-party cache, so not used
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=[mapped] if mapped else None,
                seeders=seeders,
                leechers=leechers,
                downloads=None,
                size=size,
                files_count=None,
                upload_date=self._parse_date(item.findtext("pubDate")),
                page_url=self._page_url(item.findtext("link")),
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (AttributeError, KeyError, ValueError, TypeError):
            return None

    def _page_url(self, link: str | None) -> str | None:
        """Encode torrent page link.

        Feed links contain unencoded title characters (e.g. spaces), which
        break the link. Pages are found by ID, so slug could be anything.

        Args:
            link: Link from feed

        Returns:
            Encoded link, or None if it isn't HTTP(S) link
        """
        if not link or not link.startswith(("https://", "http://")):
            return None
        return urllib.parse.quote(link.strip(), safe=":/%()-._~")

    def _parse_date(self, value: str | None) -> datetime | None:
        """Parse RSS date (e.g. "02 Nov 2026 07:30:12 +0200")."""
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

    def get_category(self, category: str | None) -> Category | None:
        """Map LimeTorrents category label to StandardCategories.

        Labels are "Category - Subcategory" or just "Category" (anime
        category label also has trailing dot, e.g. "Anime.").
        """
        if not category:
            return None

        category = category.strip().rstrip(".")
        if category in self.SUBCATEGORY_MAP:
            return self.SUBCATEGORY_MAP[category]
        return self.CATEGORY_MAP.get(category.split(" - ")[0])

    def _in_categories(
        self, result: SearchResult, parents: set[Category]
    ) -> bool:
        """Check that result belongs to one of selected parent categories."""
        return any((c.parent or c) in parents for c in result.categories or [])
