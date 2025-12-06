"""The Pirate Bay torrent search provider implementation."""

import urllib.error
import urllib.parse
import json
from datetime import datetime
from typing import Any

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, JackettCategories, Category
from ...util.decorator import log_time


class TPBProvider(BaseSearchProvider):
    """Search provider for The Pirate Bay (via apibay.org)."""

    API_URL = "https://apibay.org/q.php"

    def id(self) -> str:
        return "tpb"

    @property
    def name(self) -> str:
        return "The Pirate Bay"

    @log_time
    def _search_impl(self, query: str,
                     categories: list[Category] | None = None) -> list[
            SearchResultDTO]:
        """Search The Pirate Bay for torrents.

        Args:
            query: Search term
            categories: Category IDs to filter by (optional)

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If API request fails
        """
        if not query or not query.strip():
            return []

        # Convert Jackett category IDs to TPB category codes
        tpb_category = self._convert_categories_to_tpb(categories)

        params = {
            'q': query.strip(),
            'cat': tpb_category,
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self._urlopen(url) as response:
                data = json.loads(response.read().decode('utf-8'))

            # API returns [{"name": "No results returned"}] when no results
            if not data or (len(data) == 1 and
                            data[0].get('name') == 'No results returned'):
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

    def _parse_torrent(self, torrent: dict[str, Any]
                       ) -> SearchResultDTO | None:
        """Parse a single torrent from TPB API response."""
        try:
            info_hash = torrent.get('info_hash', '')
            if not info_hash:
                return None

            name = torrent.get('name', 'Unknown')

            size = int(torrent.get('size', 0))
            category_code = int(torrent.get('category', 0))

            magnet_link = self._build_magnet_link(
                info_hash=info_hash,
                name=name
            )

            # Parse upload date from unix timestamp
            upload_date = None
            added = torrent.get('added')
            if added:
                upload_date = datetime.fromtimestamp(int(added))

            # Build provider-specific fields
            fields = {}
            username = torrent.get('username')
            if username:
                fields['username'] = username

            status = torrent.get('status')
            if status:
                fields['status'] = status

            imdb = torrent.get('imdb')
            if imdb:
                fields['imdb'] = imdb

            # Construct page URL from torrent ID
            page_url = None
            torrent_id = torrent.get('id')
            if torrent_id:
                page_url = f"https://thepiratebay.org/description.php?id={torrent_id}"

            return SearchResultDTO(
                title=name,
                categories=self._get_category(category_code),
                seeders=int(torrent.get('seeders', 0)),
                leechers=int(torrent.get('leechers', 0)),
                size=size,
                files_count=int(torrent.get('num_files', None)),
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=upload_date,
                provider=self.name,
                provider_id=self.id(),
                page_url=page_url,
                torrent_link=None,
                fields=fields
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _convert_categories_to_tpb(
            self,
            categories: list[Category] | None) -> int:
        """Convert Jackett categories to TPB category code.

        TPB uses category codes: 100 (Audio), 200 (Video), 300 (Apps),
        400 (Games), 500 (Porn), 600 (Other)

        Args:
            categories: List of Category objects

        Returns:
            TPB category code (0 for all categories)
        """
        if not categories:
            return 0

        # Map Jackett parent category IDs to TPB codes
        jackett_to_tpb = {
            1000: 400,  # Console -> Games
            2000: 200,  # Movies -> Video
            3000: 100,  # Audio -> Audio
            4000: 300,  # PC -> Applications
            5000: 200,  # TV -> Video
            6000: 500,  # XXX -> Porn
            7000: 600,  # Books -> Other
            8000: 600,  # Other -> Other
        }

        # Try to find a matching parent category
        for category in categories:
            # Get parent category ID (first digit * 1000)
            parent_id = (category.id // 1000) * 1000
            if parent_id in jackett_to_tpb:
                return jackett_to_tpb[parent_id]

        # Default to all categories
        return 0

    # TPB category code to Jackett category mapping
    # Based on Jackett's thepiratebay.yml category mappings
    TPB_CATEGORY_MAP = {
        # Audio categories (100-199)
        100: [JackettCategories.AUDIO],
        101: [JackettCategories.AUDIO],
        102: [JackettCategories.AUDIO_AUDIOBOOK],
        103: [JackettCategories.AUDIO],
        104: [JackettCategories.AUDIO_LOSSLESS],
        199: [JackettCategories.AUDIO_OTHER],
        # Video categories (200-299)
        200: [JackettCategories.MOVIES],
        201: [JackettCategories.MOVIES],
        202: [JackettCategories.MOVIES_DVD],
        203: [JackettCategories.AUDIO_VIDEO],
        204: [JackettCategories.MOVIES_OTHER],
        205: [JackettCategories.TV],
        206: [JackettCategories.TV_OTHER],
        207: [JackettCategories.MOVIES_HD],
        208: [JackettCategories.TV_HD],
        209: [JackettCategories.MOVIES_3D],
        210: [JackettCategories.MOVIES_SD],
        211: [JackettCategories.MOVIES_UHD],
        212: [JackettCategories.TV_UHD],
        299: [JackettCategories.MOVIES_OTHER],
        # Applications (300-399)
        300: [JackettCategories.PC],
        301: [JackettCategories.PC],
        302: [JackettCategories.PC_MAC],
        303: [JackettCategories.PC],
        304: [JackettCategories.PC_MOBILE_OTHER],
        305: [JackettCategories.PC_MOBILE_IOS],
        306: [JackettCategories.PC_MOBILE_ANDROID],
        399: [JackettCategories.PC],
        # Games (400-499)
        400: [JackettCategories.CONSOLE],
        401: [JackettCategories.PC_GAMES],
        402: [JackettCategories.PC_MAC],
        403: [JackettCategories.CONSOLE_PS4],
        404: [JackettCategories.CONSOLE_XBOX],
        405: [JackettCategories.CONSOLE_WII],
        406: [JackettCategories.CONSOLE_OTHER],
        407: [JackettCategories.CONSOLE_OTHER],
        408: [JackettCategories.CONSOLE_OTHER],
        499: [JackettCategories.CONSOLE_OTHER],
        # Adult content (500-599)
        500: [JackettCategories.XXX],
        501: [JackettCategories.XXX],
        502: [JackettCategories.XXX_DVD],
        503: [JackettCategories.XXX_IMAGESET],
        504: [JackettCategories.XXX],
        505: [JackettCategories.XXX_X264],
        506: [JackettCategories.XXX],
        507: [JackettCategories.XXX_UHD],
        599: [JackettCategories.XXX_OTHER],
        # Other/Books (600-699)
        600: [JackettCategories.OTHER],
        601: [JackettCategories.BOOKS_EBOOK],
        602: [JackettCategories.BOOKS_COMICS],
        603: [JackettCategories.BOOKS],
        604: [JackettCategories.BOOKS],
        605: [JackettCategories.BOOKS],
        699: [JackettCategories.BOOKS_OTHER],
    }

    # Fallback parent categories by range
    TPB_PARENT_MAP = {
        100: JackettCategories.AUDIO,
        200: JackettCategories.MOVIES,
        300: JackettCategories.PC,
        400: JackettCategories.CONSOLE,
        500: JackettCategories.XXX,
        600: JackettCategories.OTHER,
    }

    def _get_category(self, code: int) -> list[Category]:
        """Map TPB category code to Jackett Category list.

        Based on Jackett's thepiratebay.yml category mappings:
        https://github.com/Jackett/Jackett/blob/master/src/Jackett.Common/Definitions/thepiratebay.yml

        Args:
            code: TPB category code (e.g., 101, 207, etc.)

        Returns:
            List of matching Jackett Category objects
        """
        # Try exact match first
        if code in self.TPB_CATEGORY_MAP:
            return self.TPB_CATEGORY_MAP[code]

        # Fallback to parent category by range
        parent_code = (code // 100) * 100
        if parent_code in self.TPB_PARENT_MAP:
            return [self.TPB_PARENT_MAP[parent_code]]

        # No match found
        return []

    def details_extended(self, result: SearchResultDTO) -> str:
        """Generate TPB-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with uploader details
        """
        if not result.fields:
            return ""

        md = "## Uploader\n"

        if 'username' in result.fields:
            md += f"- **Username:** {result.fields['username']}\n"

        if 'status' in result.fields:
            status = result.fields['status']
            md += "- **Status:** "

            match status:
                case 'vip':
                    md += "VIP Uploader\n"
                case 'trusted':
                    md += "Trusted Uploader\n"
                case 'member':
                    md += "Member\n"
                case _:
                    md += f"{status}\n"

        if 'imdb' in result.fields and result.fields['imdb']:
            md += "## Movie\n"

            imdb_code = result.fields['imdb']
            imdb_url = f"https://www.imdb.com/title/{imdb_code}/"
            md += f"- **IMDB:** {imdb_url}\n"

        return md
