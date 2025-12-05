"""Nyaa.si torrent search provider implementation."""

import urllib.error
import urllib.parse
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from .base_provider import BaseSearchProvider
from ...common import SearchResultDTO, TorrentCategory
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
    def short_name(self) -> str:
        return "Nyaa"

    @property
    def full_name(self) -> str:
        return "Nyaa Torrents"

    @log_time
    def _search_impl(self, query: str) -> list[SearchResultDTO]:
        """Search Nyaa.si for torrents via RSS feed.

        Args:
            query: Search term

        Returns:
            List of SearchResultDTO objects, sorted by seeders descending

        Raises:
            Exception: If RSS request fails
        """
        if not query or not query.strip():
            return []

        params = {
            'q': query.strip(),
        }

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

    def _build_fields(self, item: ET.Element, ns: dict[str, str],
                      nyaa_category: str | None) -> dict[str, str]:
        """Build provider-specific fields dictionary.

        Args:
            item: XML Element representing an RSS item
            ns: XML namespace dict
            nyaa_category: Nyaa category string

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

        if nyaa_category:
            fields['nyaa_category'] = nyaa_category

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

            # Extract and map category
            category_elem = item.find('nyaa:category', ns)
            nyaa_category = category_elem.text if category_elem is not None \
                else None
            category = self._map_category(nyaa_category)

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
            fields = self._build_fields(item, ns, nyaa_category)

            return SearchResultDTO(
                title=title,
                category=category,
                seeders=seeders,
                leechers=leechers,
                size=size,
                files_count=None,
                magnet_link=magnet_link,
                info_hash=info_hash,
                upload_date=upload_date,
                provider=self.short_name,
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

    def _map_category(self, nyaa_category: str) -> TorrentCategory:
        """Map Nyaa-specific category to basic category.

        Args:
            nyaa_category: Nyaa category string (e.g., "Anime - Raw")

        Returns:
            Basic category enum compatible with other providers
        """
        if nyaa_category is None:
            return TorrentCategory.UNKNOWN

        # Extract prefix before " - "
        prefix = nyaa_category.split(" - ")[0] \
            if " - " in nyaa_category else nyaa_category

        match prefix:
            case "Anime" | "Live Action":
                return TorrentCategory.VIDEO
            case "Audio":
                return TorrentCategory.AUDIO
            case "Literature" | "Pictures":
                return TorrentCategory.OTHER
            case "Software":
                return TorrentCategory.GAMES if "Games" in nyaa_category \
                    else TorrentCategory.SOFTWARE
            case _:
                return TorrentCategory.OTHER

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
