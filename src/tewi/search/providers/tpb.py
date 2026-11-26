# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Pirate Bay torrent search provider implementation."""

import json
import re
import urllib.error
import urllib.parse
from datetime import datetime
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
from ..util import build_magnet_link, local_time, read_response

logger = get_logger()


class TPBProvider(BaseSearchProvider):
    """Search provider for The Pirate Bay (via apibay.org)."""

    API_URL = "https://apibay.org/q.php"

    # TPB category code to Standard category mapping
    # Based on Jackett's thepiratebay.yml category mappings
    TPB_CATEGORY_MAP = {
        # Audio categories (100-199)
        100: StandardCategories.AUDIO,
        101: StandardCategories.AUDIO,
        102: StandardCategories.AUDIO_AUDIOBOOK,
        103: StandardCategories.AUDIO,
        104: StandardCategories.AUDIO_LOSSLESS,
        199: StandardCategories.AUDIO_OTHER,
        # Video categories (200-299)
        200: StandardCategories.MOVIES,
        201: StandardCategories.MOVIES,
        202: StandardCategories.MOVIES_DVD,
        203: StandardCategories.AUDIO_VIDEO,
        204: StandardCategories.MOVIES_OTHER,
        205: StandardCategories.TV,
        206: StandardCategories.TV_OTHER,
        207: StandardCategories.MOVIES_HD,
        208: StandardCategories.TV_HD,
        209: StandardCategories.MOVIES_3D,
        210: StandardCategories.MOVIES_SD,
        211: StandardCategories.MOVIES_UHD,
        212: StandardCategories.TV_UHD,
        299: StandardCategories.MOVIES_OTHER,
        # Applications (300-399)
        300: StandardCategories.PC,
        301: StandardCategories.PC,
        302: StandardCategories.PC_MAC,
        303: StandardCategories.PC,
        304: StandardCategories.PC_MOBILE_OTHER,
        305: StandardCategories.PC_MOBILE_IOS,
        306: StandardCategories.PC_MOBILE_ANDROID,
        399: StandardCategories.PC,
        # Games (400-499)
        400: StandardCategories.CONSOLE,
        401: StandardCategories.PC_GAMES,
        402: StandardCategories.PC_MAC,
        403: StandardCategories.CONSOLE_PS4,
        404: StandardCategories.CONSOLE_XBOX,
        405: StandardCategories.CONSOLE_WII,
        406: StandardCategories.CONSOLE_OTHER,
        407: StandardCategories.CONSOLE_OTHER,
        408: StandardCategories.CONSOLE_OTHER,
        499: StandardCategories.CONSOLE_OTHER,
        # Adult content (500-599)
        500: StandardCategories.XXX,
        501: StandardCategories.XXX,
        502: StandardCategories.XXX_DVD,
        503: StandardCategories.XXX_IMAGESET,
        504: StandardCategories.XXX,
        505: StandardCategories.XXX_X264,
        506: StandardCategories.XXX,
        507: StandardCategories.XXX_UHD,
        599: StandardCategories.XXX_OTHER,
        # Other/Books (600-699)
        600: StandardCategories.OTHER,
        601: StandardCategories.BOOKS_EBOOK,
        602: StandardCategories.BOOKS_COMICS,
        603: StandardCategories.BOOKS,
        604: StandardCategories.BOOKS,
        605: StandardCategories.BOOKS,
        699: StandardCategories.BOOKS_OTHER,
    }

    # Fallback parent categories by range
    TPB_PARENT_MAP = {
        100: StandardCategories.AUDIO,
        200: StandardCategories.MOVIES,
        300: StandardCategories.PC,
        400: StandardCategories.CONSOLE,
        500: StandardCategories.XXX,
        600: StandardCategories.OTHER,
    }

    _IMDB_RE = re.compile(r"tt\d+")

    @property
    def id(self) -> str:
        return "tpb"

    @property
    def name(self) -> str:
        return "The Pirate Bay"

    @property
    def short_name(self) -> str:
        return "TPB"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search The Pirate Bay for torrents.

        Args:
            query: Search term
            categories: Categories to filter by (optional)
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails or response can't be parsed
        """
        if not query or not query.strip():
            return []

        # Category 0 searches all categories
        tpb_categories = self._convert_categories_to_tpb(categories) or [0]

        params = {
            "q": query.strip(),
            "cat": ",".join(str(c) for c in tpb_categories),
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        # API returns single item with [{"id": "0"}] when no results
        if (
            len(data) == 1
            and isinstance(data[0], dict)
            and data[0].get("id") == "0"
        ):
            return []

        results = []
        for torrent in data:
            result = self._parse_torrent(torrent)
            if result:
                results.append(result)

        return results

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate TPB-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Sections with uploader details
        """
        if not result.extra:
            return []

        uploader = []

        if "username" in result.extra:
            uploader.append(("Username", result.extra["username"]))

        if "status" in result.extra:
            status = result.extra["status"]

            match status:
                case "vip":
                    status = "VIP Uploader"
                case "trusted":
                    status = "Trusted Uploader"
                case "member":
                    status = "Member"

            uploader.append(("Status", status))

        sections = [DetailsSection("Uploader", fields=tuple(uploader))]

        imdb_code = result.extra.get("imdb")
        if imdb_code:
            imdb_url = f"https://www.imdb.com/title/{imdb_code}/"
            sections.append(
                DetailsSection(
                    "Movie", fields=(("IMDB", DetailsLink(imdb_url)),)
                )
            )

        return sections

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse a single torrent from TPB API response."""
        if not isinstance(torrent, dict):
            return None

        try:
            title = torrent.get("name")
            if not title:
                return None

            info_hash = parse_info_hash(torrent.get("info_hash"))
            if not info_hash:
                return None

            category_code = int(torrent.get("category", 0))
            category = self._get_category(category_code)

            # Parse upload date from unix timestamp
            upload_date = None
            added = torrent.get("added")
            if added:
                upload_date = datetime.fromtimestamp(int(added))

            # Construct page URL from torrent ID
            page_url = None
            torrent_id = parse_count(torrent.get("id"))
            if torrent_id:
                page_url = (
                    f"https://thepiratebay.org/description.php?id={torrent_id}"
                )

            # Build provider-specific fields
            fields = {}
            username = torrent.get("username")
            if username:
                fields["username"] = username

            status = torrent.get("status")
            if status:
                fields["status"] = status

            imdb = torrent.get("imdb")
            if imdb and self._IMDB_RE.fullmatch(imdb):
                fields["imdb"] = imdb

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=(category,) if category else (),
                seeders=parse_count(torrent.get("seeders")),
                leechers=parse_count(torrent.get("leechers")),
                downloads=None,
                size=parse_count(torrent.get("size")),
                files_count=parse_count(torrent.get("num_files")),
                upload_date=local_time(upload_date),
                page_url=page_url,
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                f"TPB: skipping invalid search result {torrent.get('id')!r}"
            )
            return None

    def _convert_categories_to_tpb(
        self, categories: list[Category] | None
    ) -> list[int]:
        """Convert Standard categories to TPB category codes to search.

        Selected parent categories are searched by all TPB codes mapped to
        them or their subcategories. Range codes (e.g. 200 for Video) search
        the whole range, including other categories (e.g. TV for Movies),
        which would take API result limit, so they are only used for
        categories without other codes (e.g. 600 for Other).

        Args:
            categories: Selected categories

        Returns:
            Sorted TPB category codes, or empty list to search all
            categories
        """
        if not categories:
            return []

        tpb_categories: set[int] = set()
        for category in categories:
            parent = category.parent or category
            codes = {
                code
                for code, tpb_category in self.TPB_CATEGORY_MAP.items()
                if (tpb_category.parent or tpb_category) == parent
            }
            if not codes:
                return []
            tpb_categories |= {code for code in codes if code % 100} or codes

        return sorted(tpb_categories)

    def _get_category(self, code: int) -> Category | None:
        """Map TPB category code to Standard category.

        Based on Jackett's thepiratebay.yml category mappings:
        https://github.com/Jackett/Jackett/blob/master/src/Jackett.Common/Definitions/thepiratebay.yml

        Args:
            code: TPB category code (e.g., 101, 207, etc.)

        Returns:
            Matching Standard category, or None if code is unknown
        """
        # Try exact match first, then fall back to parent category by range
        return self.TPB_CATEGORY_MAP.get(code) or self.TPB_PARENT_MAP.get(
            (code // 100) * 100
        )
