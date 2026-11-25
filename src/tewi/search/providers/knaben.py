# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Knaben torrent search provider implementation."""

import html
import json
import re
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...util.log import log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import Category, DetailsSection, SearchResult, StandardCategories
from ..util import build_magnet_link, local_time, read_response


class KnabenProvider(BaseSearchProvider):
    """Search provider for Knaben (meta-indexer of public trackers).

    API documentation: https://knaben.org/api/v2/
    """

    API_URL = "https://api.knaben.org/v2/search"

    # Max number of results requested (API allows up to 300)
    RESULTS_LIMIT = 100

    # Max size of description shown in details
    MAX_DESCRIPTION_LINES = 30
    MAX_DESCRIPTION_CHARS = 2000

    # Knaben category IDs are hierarchical: top-level categories are
    # multiples of 1000000, subcategories of 1000 (deeper IDs, like music
    # genres, are mapped by their subcategory)

    # Top-level category mapping from Knaben to StandardCategories
    CATEGORY_MAP = {
        1000000: StandardCategories.AUDIO,  # Audio
        2000000: StandardCategories.TV,  # TV
        3000000: StandardCategories.MOVIES,  # Movies
        4000000: StandardCategories.PC,  # PC
        5000000: StandardCategories.XXX,  # XXX
        6000000: StandardCategories.TV_ANIME,  # Anime
        7000000: StandardCategories.CONSOLE,  # Console
        8000000: StandardCategories.PC_MOBILE_OTHER,  # Mobile
        9000000: StandardCategories.BOOKS,  # Books
        10000000: StandardCategories.OTHER,  # Other
    }

    # Subcategory mapping, for subcategories more specific than category
    SUBCATEGORY_MAP = {
        1001000: StandardCategories.AUDIO_MP3,  # Audio/MP3
        1002000: StandardCategories.AUDIO_LOSSLESS,  # Audio/Lossless
        1003000: StandardCategories.AUDIO_AUDIOBOOK,  # Audio/Audiobook
        1004000: StandardCategories.AUDIO_VIDEO,  # Audio/Video
        1006000: StandardCategories.AUDIO_OTHER,  # Audio/Other
        2001000: StandardCategories.TV_HD,  # TV/HD
        2002000: StandardCategories.TV_SD,  # TV/SD
        2003000: StandardCategories.TV_UHD,  # TV/UHD
        2004000: StandardCategories.TV_DOCUMENTARY,  # TV/Documentary
        2005000: StandardCategories.TV_FOREIGN,  # TV/Foreign
        2006000: StandardCategories.TV_SPORT,  # TV/Sport
        2008000: StandardCategories.TV_OTHER,  # TV/Other
        3001000: StandardCategories.MOVIES_HD,  # Movies/HD
        3002000: StandardCategories.MOVIES_SD,  # Movies/SD
        3003000: StandardCategories.MOVIES_UHD,  # Movies/UHD
        3004000: StandardCategories.MOVIES_DVD,  # Movies/DVD
        3005000: StandardCategories.MOVIES_FOREIGN,  # Movies/Foreign
        3006000: StandardCategories.MOVIES_FOREIGN,  # Movies/Bollywood
        3007000: StandardCategories.MOVIES_3D,  # Movies/3D
        3008000: StandardCategories.MOVIES_OTHER,  # Movies/Other
        4001000: StandardCategories.PC_GAMES,  # PC/Games
        4002000: StandardCategories.PC_0DAY,  # PC/Software
        4003000: StandardCategories.PC_MAC,  # PC/Mac
        5001000: StandardCategories.XXX,  # XXX/Video
        5002000: StandardCategories.XXX_IMAGESET,  # XXX/ImageSet
        5005000: StandardCategories.XXX_OTHER,  # XXX/Other
        7001000: StandardCategories.CONSOLE_PS4,  # Console/PS4
        7002000: StandardCategories.CONSOLE_PS3,  # Console/PS3
        7005000: StandardCategories.CONSOLE_PSVITA,  # Console/PS Vita
        7006000: StandardCategories.CONSOLE_PSP,  # Console/PSP
        7007000: StandardCategories.CONSOLE_XBOX360,  # Console/Xbox 360
        7008000: StandardCategories.CONSOLE_XBOX,  # Console/Xbox
        7010000: StandardCategories.CONSOLE_NDS,  # Console/NDS
        7011000: StandardCategories.CONSOLE_WII,  # Console/Wii
        7012000: StandardCategories.CONSOLE_WIIU,  # Console/WiiU
        7013000: StandardCategories.CONSOLE_3DS,  # Console/3DS
        7015000: StandardCategories.CONSOLE_OTHER,  # Console/Other
        8001000: StandardCategories.PC_MOBILE_ANDROID,  # Mobile/Android
        8002000: StandardCategories.PC_MOBILE_IOS,  # Mobile/IOS
        9001000: StandardCategories.BOOKS_EBOOK,  # Books/EBooks
        9002000: StandardCategories.BOOKS_COMICS,  # Books/Comics
        9003000: StandardCategories.BOOKS_MAGS,  # Books/Magazines
        9004000: StandardCategories.BOOKS_TECHNICAL,  # Books/Technical
        9005000: StandardCategories.BOOKS_OTHER,  # Books/Other
        10001000: StandardCategories.OTHER_MISC,  # Other/Misc
    }

    # Knaben top-level categories containing results of StandardCategories
    # parent
    PARENT_TO_KNABEN_CATEGORIES = {
        StandardCategories.CONSOLE: {7000000},
        StandardCategories.MOVIES: {3000000},
        StandardCategories.AUDIO: {1000000},
        StandardCategories.PC: {4000000, 8000000},
        StandardCategories.TV: {2000000, 6000000},
        StandardCategories.XXX: {5000000},
        StandardCategories.BOOKS: {9000000},
        StandardCategories.OTHER: {10000000},
    }

    _HTML_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
    _HTML_TAG_RE = re.compile(r"<[^>]+>")

    @property
    def id(self) -> str:
        return "knaben"

    @property
    def name(self) -> str:
        return "Knaben"

    @property
    def short_name(self) -> str:
        return "KNAB"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query or not query.strip():
            return []

        params: dict[str, Any] = {
            "q": query.strip(),
            "o": "seeders",
            "s": self.RESULTS_LIMIT,
        }

        knaben_categories = self._convert_categories_to_knaben(categories)
        if knaben_categories:
            params["c"] = ",".join(str(c) for c in knaben_categories)

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        # XXX results are hidden by API unless requested explicitly
        if not knaben_categories or 5000000 in knaben_categories:
            url += "&xxx"

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
        for torrent in data.get("hits") or []:
            result = self._parse_torrent(torrent)
            if result:
                results.append(result)
        return results

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if not result.extra:
            return []

        info = [
            (label, str(result.extra[key]))
            for key, label in (
                ("tracker", "Tracker"),
                ("k_category", "Category"),
                ("live_seeders", "Live Seeders"),
                ("live_peers", "Live Leechers"),
                ("last_seen", "Last Seen"),
            )
            if key in result.extra
        ]
        sections = [DetailsSection("Information", fields=tuple(info))]

        if "description" in result.extra:
            sections.append(
                DetailsSection("Description", text=result.extra["description"])
            )

        return sections

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        try:
            title = torrent.get("title")
            if not title or not isinstance(title, str):
                return None
            # Some trackers return titles with HTML entities
            title = html.unescape(title)

            info_hash = parse_info_hash(torrent.get("hash"))
            if not info_hash:
                return None

            magnet_link = torrent.get("magnetUrl")
            if not isinstance(magnet_link, str) or not magnet_link.startswith(
                "magnet:"
            ):
                magnet_link = build_magnet_link(info_hash=info_hash, name=title)

            categories = self.get_categories(torrent.get("categoryId"))

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=torrent.get("link") or None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=tuple(categories),
                seeders=parse_count(torrent.get("seeders")),
                leechers=parse_count(torrent.get("peers")),
                downloads=parse_count(torrent.get("grabs")),
                size=parse_count(torrent.get("bytes")),
                files_count=None,
                upload_date=local_time(self._parse_date(torrent.get("date"))),
                page_url=torrent.get("details") or None,
                freeleech=True,  # Public trackers
                extra=self._build_fields(torrent),
            )

        except (AttributeError, KeyError, ValueError, TypeError):
            return None

    def _build_fields(self, torrent: dict[str, Any]) -> dict[str, Any]:
        """Build provider-specific fields shown in details."""
        fields = {}

        tracker = torrent.get("tracker")
        if tracker:
            fields["tracker"] = tracker

        k_category = torrent.get("category")
        if k_category:
            fields["k_category"] = k_category

        if isinstance(torrent.get("liveSeeders"), int):
            fields["live_seeders"] = torrent["liveSeeders"]

        if isinstance(torrent.get("livePeers"), int):
            fields["live_peers"] = torrent["livePeers"]

        last_seen = self._parse_date(torrent.get("lastSeen"))
        if last_seen:
            fields["last_seen"] = last_seen.strftime("%Y-%m-%d %H:%M")

        description = self._format_description(
            torrent.get("description"), torrent.get("title")
        )
        if description:
            fields["description"] = description

        return fields

    def _parse_date(self, value: Any) -> datetime | None:
        """Parse ISO 8601 date string returned by API."""
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _format_description(self, value: Any, title: Any) -> str | None:
        """Convert HTML description to plain text.

        Line breaks are kept, consecutive empty lines are merged and long
        descriptions are truncated.

        Args:
            value: HTML description
            title: Torrent title

        Returns:
            Description, or None if it is empty or repeats the title
        """
        if not value or not isinstance(value, str):
            return None

        text = self._HTML_BR_RE.sub("\n", value)
        text = html.unescape(self._HTML_TAG_RE.sub(" ", text))

        lines: list[str] = []
        for line in text.splitlines():
            line = " ".join(line.split())
            if line or (lines and lines[-1]):
                lines.append(line)
        while lines and not lines[-1]:
            lines.pop()

        if not lines or " ".join(lines).strip() == html.unescape(str(title)):
            return None

        return "\n".join(self._truncate_description(lines))

    def _truncate_description(self, lines: list[str]) -> list[str]:
        """Limit description to MAX_DESCRIPTION_LINES/CHARS.

        Args:
            lines: Description lines

        Returns:
            Lines, ending with ellipsis if description was truncated
        """
        result: list[str] = []
        chars = 0
        for line in lines:
            if len(result) == self.MAX_DESCRIPTION_LINES:
                break
            if chars + len(line) > self.MAX_DESCRIPTION_CHARS:
                result.append(line[: self.MAX_DESCRIPTION_CHARS - chars])
                break
            result.append(line)
            chars += len(line)
        else:
            return result

        result[-1] = result[-1].rstrip() + "…"
        return result

    def get_categories(self, category_ids: Any) -> list[Category]:
        """Map Knaben category IDs to StandardCategories.

        Results could have several categories (e.g. from different
        trackers), so all of them are mapped. Parent categories are dropped
        when more specific category with the same parent is present.

        Args:
            category_ids: List of Knaben category IDs

        Returns:
            Mapped categories, sorted by ID
        """
        if not isinstance(category_ids, list):
            return []

        categories: set[Category] = set()
        for category_id in category_ids:
            if not isinstance(category_id, int):
                continue
            sub_id = category_id // 1000 * 1000
            parent_id = category_id // 1000000 * 1000000
            category = self.SUBCATEGORY_MAP.get(
                sub_id
            ) or self.CATEGORY_MAP.get(parent_id)
            if category:
                categories.add(category)

        specific_parents = {c.parent for c in categories if c.parent}
        return sorted(
            (c for c in categories if c not in specific_parents),
            key=lambda c: c.id,
        )

    def _convert_categories_to_knaben(
        self, categories: list[Category] | None
    ) -> list[int]:
        """Convert StandardCategories to Knaben categories to search.

        Args:
            categories: Selected categories

        Returns:
            Sorted Knaben category IDs, or empty list to search all
            categories
        """
        if not categories:
            return []

        knaben_categories: set[int] = set()
        for category in categories:
            parent = category.parent or category
            knaben_ids = self.PARENT_TO_KNABEN_CATEGORIES.get(parent)
            if not knaben_ids:
                return []
            knaben_categories |= knaben_ids

        return sorted(knaben_categories)
