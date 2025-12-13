"""TorrentsCSV.com torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...util.log import log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult
from ..util import (
    build_magnet_link,
    detect_category_from_name,
    urlopen,
)


class TorrentsCsvProvider(BaseSearchProvider):
    """Search provider for torrents-csv.com (general torrents).

    TorrentsCSV provides a public API for searching torrent metadata.
    Documentation: https://git.torrents-csv.com/heretic/torrents-csv-server
    """

    API_URL = "https://torrents-csv.com/service/search"

    @property
    def id(self) -> str:
        return "torrentscsv"

    @property
    def name(self) -> str:
        return "Torrents-CSV"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search torrents-csv.com for torrents.

        Args:
            query: Search term
            categories: Category IDs to filter by (ignored - TorrentsCSV
                       doesn't support category filtering)
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails
        """
        if not query or not query.strip():
            return []

        params = {
            "q": query.strip(),
            "size": 50,  # Limit results
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urlopen(url) as response:
                data = json.loads(response.read().decode("utf-8"))

            torrents = data.get("torrents", [])
            if not torrents:
                return []

            results = []
            for torrent in torrents:
                result = self._parse_torrent(torrent)
                if result:
                    results.append(result)

            return results

        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

    def details_extended(self, result: SearchResult) -> str:
        """Generate TorrentsCSV-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with statistics
        """
        if not result.fields:
            return ""

        md = "## Information\n"

        if "completed" in result.fields:
            completed = result.fields["completed"]
            md += f"- **Completed Downloads:** {completed}\n"

        if "scraped_date" in result.fields:
            md += f"- **Last Scraped:** {result.fields['scraped_date']}\n"

        return md

    def _parse_torrent(self, torrent: dict[str, Any]) -> SearchResult | None:
        """Parse a single torrent from TorrentsCSV API response."""
        try:
            title = torrent.get("name")
            if not title:
                return None

            info_hash = torrent.get("infohash")
            if not info_hash:
                return None

            category = detect_category_from_name(title)

            # Parse upload date from unix timestamp
            upload_date = None
            created_unix = torrent.get("created_unix")
            if created_unix:
                upload_date = datetime.fromtimestamp(created_unix)

            # Build provider-specific fields
            fields = {}
            scraped_date = torrent.get("scraped_date")
            if scraped_date:
                scraped_dt = datetime.fromtimestamp(scraped_date)
                fields["scraped_date"] = scraped_dt.strftime("%Y-%m-%d %H:%M")

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                categories=[category] if category else None,
                seeders=torrent.get("seeders"),
                leechers=torrent.get("leechers"),
                downloads=torrent.get("completed"),
                size=torrent.get("size_bytes"),
                files_count=None,
                upload_date=upload_date,
                page_url=None,
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (KeyError, ValueError, TypeError):
            return None
