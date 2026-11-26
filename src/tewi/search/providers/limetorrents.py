# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""LimeTorrents torrent search provider implementation."""

import html
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import Category, DetailsSection, SearchResult, StandardCategories
from ..util import (
    build_magnet_link,
    local_time,
    matches_query,
    query_words,
    read_response,
)

logger = get_logger()


class LimeTorrentsProvider(BaseSearchProvider):
    """Search provider for LimeTorrents (general torrents).

    The site has no API. Search uses search RSS feed, which returns up to
    40 newest results without sorting or category filtering (results are
    filtered by search manager).
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

    # Counts could have thousands separator, as on site pages
    _PEERS_RE = re.compile(r"Seeds:\s*([\d,]+)\s*,\s*Leechers\s*([\d,]+)")
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

        # Search also returns fuzzy matches (e.g. "Exemplar" for "example")
        words = query_words(query)
        items = root.findall("./channel/item")
        return [
            r
            for i in items
            if (r := self._parse_item(i)) and matches_query(r.title, words)
        ]

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if not result.extra:
            return []

        fields = []
        if "l_category" in result.extra:
            fields.append(("Category", result.extra["l_category"]))

        return [DetailsSection("Information", fields=tuple(fields))]

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
                seeders = parse_count(peers_match.group(1).replace(",", ""))
                leechers = parse_count(peers_match.group(2).replace(",", ""))

            fields = {}
            # Anime category label has trailing dot ("Anime.")
            category = (item.findtext("category") or "").strip().rstrip(".")
            if category:
                fields["l_category"] = category
            mapped = self._get_category(category)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                # .torrent link leads to third-party cache, so not used
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=(mapped,) if mapped else (),
                seeders=seeders,
                leechers=leechers,
                downloads=None,
                size=parse_count(item.findtext("size")),
                files_count=None,
                upload_date=local_time(
                    self._parse_date(item.findtext("pubDate"))
                ),
                page_url=self._page_url(item.findtext("link")),
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                "LimeTorrents: skipping invalid RSS item "
                f"{item.findtext('title')!r}"
            )
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
        link = (link or "").strip()
        if not link.startswith(("https://", "http://")):
            return None
        return urllib.parse.quote(link, safe=":/%()-._~")

    def _parse_date(self, value: str | None) -> datetime | None:
        """Parse RSS date (e.g. "02 Nov 2026 07:30:12 +0200")."""
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

    def _get_category(self, category: str | None) -> Category | None:
        """Map LimeTorrents category label to StandardCategories.

        Labels are "Category - Subcategory" or just "Category".
        """
        if not category:
            return None

        if category in self.SUBCATEGORY_MAP:
            return self.SUBCATEGORY_MAP[category]
        return self.CATEGORY_MAP.get(category.split(" - ")[0])
