"""The Pirate Bay torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...util.log import log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult, StandardCategories
from ..util import (
    build_magnet_link,
    urlopen,
)


class TPBProvider(BaseSearchProvider):
    """Search provider for The Pirate Bay (via apibay.org)."""

    API_URL = "https://apibay.org/q.php"

    # TPB category code to Standard category mapping
    # Based on Jackett's thepiratebay.yml category mappings
    TPB_CATEGORY_MAP = {
        # Audio categories (100-199)
        100: [StandardCategories.AUDIO],
        101: [StandardCategories.AUDIO],
        102: [StandardCategories.AUDIO_AUDIOBOOK],
        103: [StandardCategories.AUDIO],
        104: [StandardCategories.AUDIO_LOSSLESS],
        199: [StandardCategories.AUDIO_OTHER],
        # Video categories (200-299)
        200: [StandardCategories.MOVIES],
        201: [StandardCategories.MOVIES],
        202: [StandardCategories.MOVIES_DVD],
        203: [StandardCategories.AUDIO_VIDEO],
        204: [StandardCategories.MOVIES_OTHER],
        205: [StandardCategories.TV],
        206: [StandardCategories.TV_OTHER],
        207: [StandardCategories.MOVIES_HD],
        208: [StandardCategories.TV_HD],
        209: [StandardCategories.MOVIES_3D],
        210: [StandardCategories.MOVIES_SD],
        211: [StandardCategories.MOVIES_UHD],
        212: [StandardCategories.TV_UHD],
        299: [StandardCategories.MOVIES_OTHER],
        # Applications (300-399)
        300: [StandardCategories.PC],
        301: [StandardCategories.PC],
        302: [StandardCategories.PC_MAC],
        303: [StandardCategories.PC],
        304: [StandardCategories.PC_MOBILE_OTHER],
        305: [StandardCategories.PC_MOBILE_IOS],
        306: [StandardCategories.PC_MOBILE_ANDROID],
        399: [StandardCategories.PC],
        # Games (400-499)
        400: [StandardCategories.CONSOLE],
        401: [StandardCategories.PC_GAMES],
        402: [StandardCategories.PC_MAC],
        403: [StandardCategories.CONSOLE_PS4],
        404: [StandardCategories.CONSOLE_XBOX],
        405: [StandardCategories.CONSOLE_WII],
        406: [StandardCategories.CONSOLE_OTHER],
        407: [StandardCategories.CONSOLE_OTHER],
        408: [StandardCategories.CONSOLE_OTHER],
        499: [StandardCategories.CONSOLE_OTHER],
        # Adult content (500-599)
        500: [StandardCategories.XXX],
        501: [StandardCategories.XXX],
        502: [StandardCategories.XXX_DVD],
        503: [StandardCategories.XXX_IMAGESET],
        504: [StandardCategories.XXX],
        505: [StandardCategories.XXX_X264],
        506: [StandardCategories.XXX],
        507: [StandardCategories.XXX_UHD],
        599: [StandardCategories.XXX_OTHER],
        # Other/Books (600-699)
        600: [StandardCategories.OTHER],
        601: [StandardCategories.BOOKS_EBOOK],
        602: [StandardCategories.BOOKS_COMICS],
        603: [StandardCategories.BOOKS],
        604: [StandardCategories.BOOKS],
        605: [StandardCategories.BOOKS],
        699: [StandardCategories.BOOKS_OTHER],
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

    # Map Standard parent category IDs to TPB codes
    STD_TO_TPB_MAP = {
        1000: 400,  # Console -> Games
        2000: 200,  # Movies -> Video
        3000: 100,  # Audio -> Audio
        4000: 300,  # PC -> Applications
        5000: 200,  # TV -> Video
        6000: 500,  # XXX -> Porn
        7000: 600,  # Books -> Other
        8000: 600,  # Other -> Other
    }

    @property
    def id(self) -> str:
        return "tpb"

    @property
    def name(self) -> str:
        return "The Pirate Bay"

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
            categories: Category IDs to filter by (optional)
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails
        """
        if not query or not query.strip():
            return []

        # Convert Standard category IDs to TPB category codes
        tpb_category = self._convert_categories_to_tpb(categories)

        params = {
            "q": query.strip(),
            "cat": tpb_category,
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urlopen(url) as response:
                data = json.loads(response.read().decode("utf-8"))

            # API returns [{"name": "No results returned"}] when no results
            if not data or (
                len(data) == 1 and data[0].get("name") == "No results returned"
            ):
                return []

            results = []
            for torrent in data:
                result = self._parse_torrent(torrent)
                if result:
                    results.append(result)

            return results

        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

    def details_extended(self, result: SearchResult) -> str:
        """Generate TPB-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with uploader details
        """
        if not result.fields:
            return ""

        md = "## Uploader\n"

        if "username" in result.fields:
            md += f"- **Username:** {result.fields['username']}\n"

        if "status" in result.fields:
            status = result.fields["status"]
            md += "- **Status:** "

            match status:
                case "vip":
                    md += "VIP Uploader\n"
                case "trusted":
                    md += "Trusted Uploader\n"
                case "member":
                    md += "Member\n"
                case _:
                    md += f"{status}\n"

        if "imdb" in result.fields and result.fields["imdb"]:
            md += "## Movie\n"

            imdb_code = result.fields["imdb"]
            imdb_url = f"https://www.imdb.com/title/{imdb_code}/"
            md += f"- **IMDB:** {imdb_url}\n"

        return md

    def _parse_torrent(self, torrent: dict[str, Any]) -> SearchResult | None:
        """Parse a single torrent from TPB API response."""
        try:
            title = torrent.get("name")
            if not title:
                return None

            info_hash = torrent.get("info_hash")
            if not info_hash:
                return None

            category_code = int(torrent.get("category", 0))
            categories = self._get_category(category_code)

            # Parse upload date from unix timestamp
            upload_date = None
            added = torrent.get("added")
            if added:
                upload_date = datetime.fromtimestamp(int(added))

            # Construct page URL from torrent ID
            page_url = None
            torrent_id = torrent.get("id")
            if torrent_id:
                page_url = (
                    f"https://thepiratebay.org/description.php?id={torrent_id}"
                )

            # Get files_count if available
            files_count = torrent.get("num_files")
            if files_count is not None:
                files_count = int(files_count)

            # Build provider-specific fields
            fields = {}
            username = torrent.get("username")
            if username:
                fields["username"] = username

            status = torrent.get("status")
            if status:
                fields["status"] = status

            imdb = torrent.get("imdb")
            if imdb:
                fields["imdb"] = imdb

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                categories=categories,
                seeders=int(torrent.get("seeders")),
                leechers=int(torrent.get("leechers")),
                downloads=None,
                size=int(torrent.get("size")),
                files_count=files_count,
                upload_date=upload_date,
                page_url=page_url,
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _convert_categories_to_tpb(
        self, categories: list[Category] | None
    ) -> int:
        """Convert Standard categories to TPB category code.

        TPB uses category codes: 100 (Audio), 200 (Video), 300 (Apps),
        400 (Games), 500 (Porn), 600 (Other)

        Args:
            categories: List of Category objects

        Returns:
            TPB category code (0 for all categories)
        """
        if not categories:
            return 0

        # Try to find a matching parent category
        for category in categories:
            # Get parent category ID (first digit * 1000)
            parent_id = (category.id // 1000) * 1000
            if parent_id in self.STD_TO_TPB_MAP:
                return self.STD_TO_TPB_MAP[parent_id]

        # Default to all categories
        return 0

    def _get_category(self, code: int) -> list[Category] | None:
        """Map TPB category code to Standard Category list.

        Based on Jackett's thepiratebay.yml category mappings:
        https://github.com/Jackett/Jackett/blob/master/src/Jackett.Common/Definitions/thepiratebay.yml

        Args:
            code: TPB category code (e.g., 101, 207, etc.)

        Returns:
            List of matching Standard Category objects
        """
        # Try exact match first
        if code in self.TPB_CATEGORY_MAP:
            return self.TPB_CATEGORY_MAP[code]

        # Fallback to parent category by range
        parent_code = (code // 100) * 100
        if parent_code in self.TPB_PARENT_MAP:
            return [self.TPB_PARENT_MAP[parent_code]]

        # No match found
        return None
