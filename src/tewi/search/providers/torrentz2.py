"""Torrentz2 torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from typing import Any

from ...util.log import log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult
from ..util import (
    build_magnet_link,
    detect_category_from_name,
    urlopen,
)


class Torrentz2Provider(BaseSearchProvider):
    """Search provider for Torrentz2 (general torrents).

    API documentation: https://torrentz2.nz/api
    """

    API_URL = "https://torrentz2.nz/api/v1/search"

    @property
    def id(self) -> str:
        return "torrentz2"

    @property
    def name(self) -> str:
        return "Torrentz2"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query or not query.strip():
            return []

        params = {
            "q": query.strip(),
            "limit": 100,  # Max limit (default to 20)
            "sort": "seeders",
        }

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urlopen(url) as response:
                data = json.loads(response.read().decode("utf-8"))

            success = data.get("success")
            if not success:
                return []

            torrents = data.get("results", [])
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
        if not result.fields:
            return ""

        md = "## Information\n"

        if "verified" in result.fields:
            verified = "Yes" if result.fields["verified"] else "No"
            md += f"- **Verified:** {verified}\n"

        return md

    def _parse_torrent(self, torrent: dict[str, Any]) -> SearchResult | None:
        try:
            title = torrent.get("title")
            if not title:
                return None

            info_hash = torrent.get("infohash")
            if not info_hash:
                return None

            # cat = torrent.get("category")
            # sub_cat = torrent.get("subCategory")

            # TODO: map categories from site
            category = detect_category_from_name(title)

            # Build provider-specific fields
            fields = {}

            tid = torrent.get("id")

            fields["torrent_id"] = tid
            fields["verified"] = torrent.get("verified")

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
                downloads=torrent.get("downloads"),
                size=torrent.get("size"),
                files_count=None,
                upload_date=None,
                page_url=f"https://torrentz2.nz/torrent/{tid}",
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (KeyError, ValueError, TypeError):
            return None
