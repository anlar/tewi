# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""TorrentsCSV.com torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import Category, DetailsSection, SearchResult
from ..util import (
    build_magnet_link,
    detect_category_from_name,
    parse_timestamp,
    read_response,
)

logger = get_logger()


class TorrentsCsvProvider(BaseSearchProvider):
    """Search provider for torrents-csv.com (general torrents).

    TorrentsCSV provides a public API for searching torrent metadata.
    Documentation: https://git.torrents-csv.com/heretic/torrents-csv-server
    """

    API_URL = "https://torrents-csv.com/service/search"

    # API rejects shorter queries with HTTP 400, length is in UTF-8 bytes
    # (e.g. 2-character Japanese query is accepted)
    MIN_QUERY_SIZE = 3  # bytes

    # API returns pages of 25 results, ignoring "size" parameter, so
    # several pages are loaded one by one
    MAX_PAGES = 4

    @property
    def id(self) -> str:
        return "torrentscsv"

    @property
    def name(self) -> str:
        return "Torrents-CSV"

    @property
    def short_name(self) -> str:
        return "T-CSV"

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
            categories: Categories to filter by (ignored - TorrentsCSV
                doesn't support category filtering, results are filtered
                by category detected from name)
            indexers: Indexer IDs (ignored - not a meta-provider)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails or response can't be parsed
        """
        query = (query or "").strip()
        if len(query.encode("utf-8")) < self.MIN_QUERY_SIZE:
            return []

        results = []
        after = None
        for page in range(self.MAX_PAGES):
            try:
                torrents, after = self._fetch_page(query, after)
            except Exception as e:
                if page == 0:
                    raise
                # Keep results of loaded pages
                logger.warning(
                    f"Torrents-CSV: failed to load page {page + 1}: {e}"
                )
                break

            for torrent in torrents:
                result = self._parse_torrent(torrent)
                if result:
                    results.append(result)

            if not torrents or after is None:
                break

        return results

    def _fetch_page(
        self, query: str, after: int | None
    ) -> tuple[list[Any], int | None]:
        """Fetch a page of search results.

        Pages are ordered by result ID (more seeded torrents first), next
        page starts after the last ID of previous one.

        Args:
            query: Search term
            after: ID to load results after, or None for the first page

        Returns:
            Torrents of the page and ID to load the next page after, or
            None if there are no more pages

        Raises:
            Exception: If API request fails or response can't be parsed
        """
        params: dict[str, str | int] = {"q": query}
        if after is not None:
            params["after"] = after

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        if not isinstance(data, dict):
            raise Exception("Failed to parse API response: not an object")

        torrents = data.get("torrents") or []
        if not isinstance(torrents, list):
            raise Exception("Failed to parse API response: invalid torrents")

        # Guard against cursor not moving forward, which would load the
        # same page again
        next_after = parse_count(data.get("next"))
        if next_after is not None and after is not None and next_after <= after:
            next_after = None

        return torrents, next_after

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate TorrentsCSV-specific details for right column.

        Args:
            result: Search result to format

        Returns:
            Sections with statistics
        """
        if not result.extra:
            return []

        fields = []
        scraped_date = result.extra.get("scraped_date")
        if isinstance(scraped_date, datetime):
            fields.append(
                ("Last Scraped", scraped_date.strftime("%Y-%m-%d %H:%M"))
            )

        return [DetailsSection("Information", fields=tuple(fields))]

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse a single torrent from TorrentsCSV API response."""
        if not isinstance(torrent, dict):
            return None

        try:
            title = torrent.get("name")
            if not isinstance(title, str) or not title.strip():
                return None

            info_hash = parse_info_hash(torrent.get("infohash"))
            if not info_hash:
                return None

            category = detect_category_from_name(title)

            # Build provider-specific fields
            fields: dict[str, object] = {}
            scraped_date = parse_timestamp(torrent.get("scraped_date"))
            if scraped_date:
                fields["scraped_date"] = scraped_date

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
                downloads=parse_count(torrent.get("completed")),
                size=parse_count(torrent.get("size_bytes")),
                files_count=None,
                upload_date=parse_timestamp(torrent.get("created_unix")),
                page_url=None,
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                "Torrents-CSV: skipping invalid search result "
                f"{torrent.get('infohash')!r}"
            )
            return None
