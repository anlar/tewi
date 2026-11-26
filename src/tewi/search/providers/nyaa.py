# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Nyaa.si torrent search provider implementation."""

import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import Category, DetailsSection, SearchResult, StandardCategories
from ..util import build_magnet_link, local_time, read_response

logger = get_logger()


class NyaaProvider(BaseSearchProvider):
    """Search provider for Nyaa.si (anime torrents).

    Nyaa.si provides an RSS feed with custom XML namespace for searching.
    The feed includes seeders, leechers, and other metadata.
    """

    RSS_URL = "https://nyaa.si/?page=rss"

    # Trackers of Nyaa magnet links, in the same order
    TRACKERS = [
        "http://nyaa.tracker.wf:7777/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
    ]

    NS = {"nyaa": "https://nyaa.si/xmlns/nyaa"}

    ALL_CATEGORIES = "0_0"

    # Mapping based on Jackett's nyaasi.yml categorymappings
    NYAA_CATEGORY_MAP = {
        # Anime categories (1_x)
        "1_0": StandardCategories.TV_ANIME,  # Anime
        "1_1": StandardCategories.TV_ANIME,  # Anime - AMV
        "1_2": StandardCategories.TV_ANIME,  # Anime - English-translated
        "1_3": StandardCategories.TV_ANIME,  # Anime - Non-English
        "1_4": StandardCategories.TV_ANIME,  # Anime - Raw
        # Audio categories (2_x)
        "2_0": StandardCategories.AUDIO,  # Audio
        "2_1": StandardCategories.AUDIO_LOSSLESS,  # Audio - Lossless
        "2_2": StandardCategories.AUDIO,  # Audio - Lossy
        # Literature categories (3_x)
        "3_0": StandardCategories.BOOKS,  # Literature
        "3_1": StandardCategories.BOOKS,  # Literature - English
        "3_2": StandardCategories.BOOKS,  # Literature - Non-English
        "3_3": StandardCategories.BOOKS,  # Literature - Raw
        # Live Action categories (4_x)
        "4_0": StandardCategories.TV,  # Live Action
        "4_1": StandardCategories.TV,  # Live Action - English
        "4_2": StandardCategories.TV,  # Live Action - Idol/PV
        "4_3": StandardCategories.TV,  # Live Action - Non-English
        "4_4": StandardCategories.TV,  # Live Action - Raw
        # Pictures categories (5_x)
        "5_0": StandardCategories.OTHER,  # Pictures
        "5_1": StandardCategories.OTHER,  # Pictures - Graphics
        "5_2": StandardCategories.OTHER,  # Pictures - Photos
        # Software categories (6_x)
        "6_0": StandardCategories.PC,  # Software
        "6_1": StandardCategories.PC_ISO,  # Software - Applications
        "6_2": StandardCategories.PC_GAMES,  # Software - Games
    }

    # Binary size units used by Nyaa (Jinja filesizeformat)
    SIZE_UNITS = {
        "Byte": 1,
        "Bytes": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
        "PiB": 1024**5,
    }

    _SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s+(\w+)")

    @property
    def id(self) -> str:
        return "nyaa"

    @property
    def name(self) -> str:
        return "Nyaa Torrents"

    @property
    def short_name(self) -> str:
        return "Nyaa"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search Nyaa.si for torrents via RSS feed.

        Args:
            query: Search term
            categories: Categories to filter by (optional)
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If RSS request fails or feed can't be parsed
        """
        query = query.strip() if query else ""
        if not query:
            return []

        nyaa_category = self.ALL_CATEGORIES
        if categories:
            nyaa_category = self._convert_categories_to_nyaa(categories)
            if nyaa_category is None:
                logger.debug(
                    "Nyaa: skipping search, no Nyaa categories for "
                    f"{[c.name for c in categories]}"
                )
                return []

        params = {
            "q": query,
            "c": nyaa_category,
        }

        url = f"{self.RSS_URL}&{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = read_response(response)
            # Parse RSS XML from bytes, so invalid encoding is a ParseError.
            # ElementTree doesn't load external entities or DTDs, and expat
            # (>= 2.4.1) limits entity expansion
            root = ET.fromstring(data)  # noqa: S314
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except ET.ParseError as e:
            raise Exception(f"Failed to parse RSS feed: {e}")

        results = []
        for item in root.iter("item"):
            result = self._parse_item(item)
            if result:
                results.append(result)

        return results

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate Nyaa-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Sections with Nyaa-specific details
        """
        if not result.extra:
            return []

        fields = [
            (label, str(result.extra[key]))
            for key, label in (
                ("nyaa_category", "Nyaa Category"),
                ("comments", "Comments"),
                ("trusted", "Trusted"),
                ("remake", "Remake"),
            )
            if key in result.extra
        ]

        return [DetailsSection("Information", fields=tuple(fields))]

    def _parse_item(self, item: ET.Element) -> SearchResult | None:
        """Parse a single RSS item from Nyaa feed.

        Args:
            item: XML Element representing an RSS item

        Returns:
            SearchResult or None if item is invalid
        """
        page_url = item.findtext("guid")
        # Page URL ends with torrent ID: https://nyaa.si/view/<id>
        torrent_id = page_url.rsplit("/", 1)[-1] if page_url else None

        try:
            title = item.findtext("title")
            if not title:
                return None

            info_hash = parse_info_hash(
                item.findtext("nyaa:infoHash", None, self.NS)
            )
            if not info_hash:
                return None

            category = self._get_category(
                item.findtext("nyaa:categoryId", None, self.NS)
            )

            upload_date = None
            pub_date = item.findtext("pubDate")
            if pub_date:
                upload_date = parsedate_to_datetime(pub_date)
                # Nyaa writes UTC as "-0000", which is parsed as naive date
                if upload_date.tzinfo is None:
                    upload_date = upload_date.replace(tzinfo=timezone.utc)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(
                    info_hash=info_hash, name=title, trackers=self.TRACKERS
                ),
                torrent_link=item.findtext("link") or None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=(category,) if category else (),
                seeders=parse_count(
                    item.findtext("nyaa:seeders", None, self.NS)
                ),
                leechers=parse_count(
                    item.findtext("nyaa:leechers", None, self.NS)
                ),
                downloads=parse_count(
                    item.findtext("nyaa:downloads", None, self.NS)
                ),
                size=self._parse_size(
                    item.findtext("nyaa:size", None, self.NS)
                ),
                files_count=None,
                upload_date=local_time(upload_date),
                page_url=page_url or None,
                freeleech=True,  # Public tracker
                extra=self._build_fields(item),
            )

        except Exception:
            logger.exception(
                f"Nyaa: skipping invalid search result {torrent_id!r}"
            )
            return None

    def _parse_size(self, value: str | None) -> int | None:
        """Parse human-readable size to bytes.

        Args:
            value: Size like "21.6 GiB", "446.1 MiB" or "512 Bytes"

        Returns:
            Size in bytes, or None if size is missing or invalid
        """
        match = self._SIZE_RE.fullmatch(value.strip()) if value else None
        if not match or match.group(2) not in self.SIZE_UNITS:
            return None
        return int(float(match.group(1)) * self.SIZE_UNITS[match.group(2)])

    def _convert_categories_to_nyaa(
        self, categories: list[Category]
    ) -> str | None:
        """Convert Standard categories to Nyaa category code to search.

        Nyaa searches only by one category, so it's used when all selected
        categories are in the same Nyaa group (e.g. '2_0' for Audio).
        Otherwise all categories are searched and results are filtered by
        selected categories later (e.g. TV has both Anime and Live Action
        groups).

        Args:
            categories: Selected categories

        Returns:
            Nyaa category code ('0_0' for all categories), or None if
            Nyaa has no selected categories (e.g. Movies)
        """
        selected = {category.parent or category for category in categories}
        groups = {
            code.split("_")[0]
            for code, nyaa_category in self.NYAA_CATEGORY_MAP.items()
            if (nyaa_category.parent or nyaa_category) in selected
        }

        if not groups:
            return None
        if len(groups) > 1:
            return self.ALL_CATEGORIES
        return f"{groups.pop()}_0"

    def _get_category(self, category_id: str | None) -> Category | None:
        """Map Nyaa category ID to Standard category.

        Based on Jackett's nyaasi.yml category mappings:
        https://github.com/Jackett/Jackett/blob/master/src/Jackett.Common/Definitions/nyaasi.yml

        Args:
            category_id: Nyaa category ID (e.g., "1_4" for Anime - Raw)

        Returns:
            Matching Standard category, or None if ID is unknown
        """
        if not category_id:
            return None
        return self.NYAA_CATEGORY_MAP.get(category_id)

    def _build_fields(self, item: ET.Element) -> dict[str, object]:
        """Build provider-specific fields dictionary.

        Args:
            item: XML Element representing an RSS item

        Returns:
            Dictionary of provider-specific fields
        """
        fields: dict[str, object] = {}
        for key, tag in (
            ("comments", "nyaa:comments"),
            ("trusted", "nyaa:trusted"),
            ("remake", "nyaa:remake"),
            ("nyaa_category", "nyaa:category"),
        ):
            value = item.findtext(tag, None, self.NS)
            if value:
                fields[key] = value
        return fields
