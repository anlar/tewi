"""Nyaa.si torrent search provider implementation."""

import urllib.error
import urllib.parse
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, JackettCategories, Category
from ...util.decorator import log_time


class NyaaProvider(BaseSearchProvider):
    """Search provider for Nyaa.si (anime torrents).

    Nyaa.si provides an RSS feed with custom XML namespace for searching.
    The feed includes seeders, leechers, and other metadata.
    """

    RSS_URL = "https://nyaa.si/?page=rss"

    # Common public trackers for anime torrents
    TRACKERS = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://exodus.desync.com:6969/announce",
        "http://nyaa.tracker.wf:7777/announce",
    ]

    def id(self) -> str:
        return "nyaa"

    @property
    def name(self) -> str:
        return "Nyaa Torrents"

    @log_time
    def _search_impl(self, query: str,
                     categories: list[Category] | None = None) -> list[
            SearchResultDTO]:
        """Search Nyaa.si for torrents via RSS feed.

        Args:
            query: Search term
            categories: Category IDs to filter by (optional)

        Returns:
            List of SearchResultDTO objects, sorted by seeders descending

        Raises:
            Exception: If RSS request fails
        """
        if not query or not query.strip():
            return []

        # Convert Jackett category IDs to Nyaa category codes
        nyaa_category = self._convert_categories_to_nyaa(categories)

        params = {
            'q': query.strip(),
        }
        if nyaa_category:
            params['c'] = nyaa_category

        url = f"{self.RSS_URL}&{urllib.parse.urlencode(params)}"

        try:
            with self._urlopen(url) as response:
                data = response.read().decode('utf-8')

            # Parse RSS XML
            root = ET.fromstring(data)

            # Register Nyaa namespace
            ns = {'nyaa': 'https://nyaa.si/xmlns/nyaa'}

            items = root.findall('.//item')
            if not items:
                return []

            results = []
            for item in items:
                result = self._parse_item(item, ns)
                if result:
                    results.append(result)

            return results

        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except ET.ParseError as e:
            raise Exception(f"Failed to parse RSS feed: {e}")

    def _build_fields(self, item: ET.Element,
                      ns: dict[str, str]) -> dict[str, str]:
        """Build provider-specific fields dictionary.

        Args:
            item: XML Element representing an RSS item
            ns: XML namespace dict

        Returns:
            Dictionary of provider-specific fields
        """
        fields = {}
        downloads_elem = item.find('nyaa:downloads', ns)
        if downloads_elem is not None and downloads_elem.text:
            fields['downloads'] = downloads_elem.text

        comments_elem = item.find('nyaa:comments', ns)
        if comments_elem is not None and comments_elem.text:
            fields['comments'] = comments_elem.text

        trusted_elem = item.find('nyaa:trusted', ns)
        if trusted_elem is not None and trusted_elem.text:
            fields['trusted'] = trusted_elem.text

        remake_elem = item.find('nyaa:remake', ns)
        if remake_elem is not None and remake_elem.text:
            fields['remake'] = remake_elem.text

        category_elem = item.find('nyaa:category', ns)
        if category_elem is not None and category_elem.text:
            fields['nyaa_category'] = category_elem.text

        return fields

    def _parse_item(self, item: ET.Element,
                    ns: dict[str, str]) -> SearchResultDTO | None:
        """Parse a single RSS item from Nyaa feed.

        Args:
            item: XML Element representing an RSS item
            ns: XML namespace dict

        Returns:
            SearchResultDTO or None if parsing fails
        """
        try:
            title_elem = item.find('title')
            if title_elem is None or not title_elem.text:
                return None

            title = title_elem.text

            # Extract info hash
            hash_elem = item.find('nyaa:infoHash', ns)
            if hash_elem is None or not hash_elem.text:
                return None
            info_hash = hash_elem.text

            # Extract seeders and leechers
            seeders_elem = item.find('nyaa:seeders', ns)
            leechers_elem = item.find('nyaa:leechers', ns)
            seeders = int(seeders_elem.text) if seeders_elem is not None \
                else 0
            leechers = int(leechers_elem.text) if leechers_elem is not None \
                else 0

            # Extract category ID
            category_id_elem = item.find('nyaa:categoryId', ns)
            category_id = category_id_elem.text if category_id_elem is not None \
                else None
            category = self._map_category_by_id(category_id)

            # Extract and parse size
            size_elem = item.find('nyaa:size', ns)
            size = self._parse_size(size_elem.text) if size_elem is not None \
                else 0

            # Extract and parse upload date
            pubdate_elem = item.find('pubDate')
            upload_date = None
            if pubdate_elem is not None and pubdate_elem.text:
                try:
                    # RFC 2822 format: "Mon, 17 Nov 2025 08:08:30 -0000"
                    upload_date = datetime.strptime(
                        pubdate_elem.text,
                        '%a, %d %b %Y %H:%M:%S %z'
                    )
                except ValueError:
                    pass

            # Build magnet link
            magnet_link = self._build_magnet_link(
                info_hash=info_hash,
                name=title,
                trackers=self.TRACKERS
            )

            # Extract page URL from link element
            page_url = None
            link_elem = item.find('guid')
            if link_elem is not None and link_elem.text:
                page_url = link_elem.text

            # Build provider-specific fields
            fields = self._build_fields(item, ns)

            return SearchResultDTO(
                title=title,
                categories=category,
                seeders=seeders,
                leechers=leechers,
                size=size,
                files_count=None,
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=upload_date,
                provider=self.name,
                provider_id=self.id(),
                page_url=page_url,
                torrent_link=None,
                fields=fields
            )

        except (KeyError, ValueError, TypeError, AttributeError):
            return None

    def _parse_size(self, size_str: str) -> int:
        """Parse human-readable size to bytes.

        Args:
            size_str: Size string like "21.6 GiB" or "446.1 MiB"

        Returns:
            Size in bytes
        """
        # Match pattern: "1.4 GiB"
        match = re.match(r'([\d.]+)\s+(B|KiB|MiB|GiB|TiB)', size_str)
        if not match:
            return 0

        value = float(match.group(1))
        unit = match.group(2)

        # Binary units (1024-based)
        multipliers = {
            'B': 1,
            'KiB': 1024,
            'MiB': 1024 ** 2,
            'GiB': 1024 ** 3,
            'TiB': 1024 ** 4,
        }

        return int(value * multipliers.get(unit, 1))

    def _convert_categories_to_nyaa(
            self,
            categories: list[Category] | None) -> str | None:
        """Convert Jackett categories to Nyaa category code.

        Nyaa uses category codes like '1_0' (Anime), '2_0' (Audio), etc.

        Args:
            categories: List of Category objects

        Returns:
            Nyaa category code or None for all categories
        """
        if not categories:
            return None

        # Map Jackett category IDs to Nyaa codes
        jackett_to_nyaa = {
            # TV/Anime categories
            5070: '1_0',  # TV/Anime -> Anime
            5000: '1_0',  # TV -> Anime (Nyaa is anime-focused)
            # Audio categories
            3000: '2_0',  # Audio -> Audio
            3040: '2_1',  # Audio/Lossless -> Audio - Lossless
            # Books categories
            7000: '3_0',  # Books -> Literature
            # Software/PC categories
            4000: '6_0',  # PC -> Software
            4020: '6_1',  # PC/ISO -> Software - Applications
            4050: '6_2',  # PC/Games -> Software - Games
        }

        # Try to find a matching category
        for category in categories:
            if category.id in jackett_to_nyaa:
                return jackett_to_nyaa[category.id]
            # Try parent category
            parent_id = (category.id // 1000) * 1000
            if parent_id in jackett_to_nyaa:
                return jackett_to_nyaa[parent_id]

        # Default to all categories
        return None

    def _map_category_by_id(self, category_id: str | None) -> list[Category]:
        """Map Nyaa categoryId to Jackett Category list.

        Based on Jackett's nyaasi.yml category mappings:
        https://github.com/Jackett/Jackett/blob/master/src/Jackett.Common/Definitions/nyaasi.yml

        Args:
            category_id: Nyaa category ID (e.g., "1_4" for Anime - Raw)

        Returns:
            List of matching Jackett Category objects
        """
        if not category_id:
            return []

        # Mapping based on Jackett's nyaasi.yml categorymappings
        # Format: categoryId -> [Jackett Categories]
        category_map = {
            # Anime categories (1_x) - map to TV/Anime
            '1_0': [JackettCategories.TV_ANIME],  # Anime
            '1_1': [JackettCategories.TV_ANIME],  # Anime - AMV
            '1_2': [JackettCategories.TV_ANIME],  # Anime - English-translated
            '1_3': [JackettCategories.TV_ANIME],  # Anime - Non-English
            '1_4': [JackettCategories.TV_ANIME],  # Anime - Raw

            # Audio categories (2_x)
            '2_0': [JackettCategories.AUDIO],  # Audio
            '2_1': [JackettCategories.AUDIO_LOSSLESS],  # Audio - Lossless
            '2_2': [JackettCategories.AUDIO],  # Audio - Lossy

            # Literature categories (3_x)
            '3_0': [JackettCategories.BOOKS],  # Literature
            '3_1': [JackettCategories.BOOKS],  # Literature - English
            '3_2': [JackettCategories.BOOKS],  # Literature - Non-English
            '3_3': [JackettCategories.BOOKS],  # Literature - Raw

            # Live Action categories (4_x)
            '4_0': [JackettCategories.TV],  # Live Action
            '4_1': [JackettCategories.TV],  # Live Action - English
            '4_2': [JackettCategories.TV],  # Live Action - Idol/PV
            '4_3': [JackettCategories.TV],  # Live Action - Non-English
            '4_4': [JackettCategories.TV],  # Live Action - Raw

            # Pictures categories (5_x)
            '5_0': [JackettCategories.OTHER],  # Pictures
            '5_1': [JackettCategories.OTHER],  # Pictures - Graphics
            '5_2': [JackettCategories.OTHER],  # Pictures - Photos

            # Software categories (6_x)
            '6_0': [JackettCategories.PC],  # Software
            '6_1': [JackettCategories.PC_ISO],  # Software - Applications
            '6_2': [JackettCategories.PC_GAMES],  # Software - Games
        }

        return category_map.get(category_id, [])

    def details_extended(self, result: SearchResultDTO) -> str:
        """Generate Nyaa-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with Nyaa-specific details
        """
        if not result.fields:
            return ""

        md = "## Information\n"

        if 'nyaa_category' in result.fields:
            md += f"- **Category:** {result.fields['nyaa_category']}\n"

        if 'downloads' in result.fields:
            md += f"- **Downloads:** {result.fields['downloads']}\n"

        if 'comments' in result.fields:
            md += f"- **Comments:** {result.fields['comments']}\n"

        if 'trusted' in result.fields:
            trusted_val = result.fields['trusted']
            md += f"- **Trusted:** {trusted_val}\n"

        if 'remake' in result.fields:
            remake_val = result.fields['remake']
            md += f"- **Remake:** {remake_val}\n"

        return md
