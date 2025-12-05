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
    def short_name(self) -> str:
        return "TPB"

    @property
    def full_name(self) -> str:
        return "The Pirate Bay"

    @log_time
    def _search_impl(self, query: str,
                     categories: list[str] | None = None) -> list[
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
                provider=self.short_name,
                provider_id=self.id(),
                page_url=page_url,
                torrent_link=None,
                fields=fields
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _convert_categories_to_tpb(
            self,
            categories: list[str] | None) -> int:
        """Convert Jackett category IDs to TPB category code.

        TPB uses category codes: 100 (Audio), 200 (Video), 300 (Apps),
        400 (Games), 500 (Porn), 600 (Other)

        Args:
            categories: List of Jackett category ID strings

        Returns:
            TPB category code (0 for all categories)
        """
        if not categories:
            return 0

        # Map Jackett parent category IDs to TPB codes
        jackett_to_tpb = {
            '1000': 400,  # Console -> Games
            '2000': 200,  # Movies -> Video
            '3000': 100,  # Audio -> Audio
            '4000': 300,  # PC -> Applications
            '5000': 200,  # TV -> Video
            '6000': 500,  # XXX -> Porn
            '7000': 600,  # Books -> Other
            '8000': 600,  # Other -> Other
        }

        # Try to find a matching parent category
        for cat_id in categories:
            # Get parent category ID (first digit + '000')
            parent_id = str((int(cat_id) // 1000) * 1000)
            if parent_id in jackett_to_tpb:
                return jackett_to_tpb[parent_id]

        # Default to all categories
        return 0

    def _get_category(self, code: str) -> list[Category]:
        """Map TPB category code to Jackett Category list.

        TPB uses category codes like 100 (Audio), 200 (Video), etc.

        Args:
            code: TPB category code

        Returns:
            List containing matching parent Category, or empty list
        """
        c = code // 100

        match c:
            case 1:
                return [JackettCategories.AUDIO]
            case 2:
                return [JackettCategories.MOVIES]
            case 3:
                return [JackettCategories.PC]
            case 4:
                return [JackettCategories.CONSOLE]
            case 5:
                return [JackettCategories.XXX]
            case 6:
                return [JackettCategories.OTHER]
            case _:
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
