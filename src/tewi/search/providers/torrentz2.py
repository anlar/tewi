"""Torrentz2 torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from typing import Any

from ...util.log import log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult, StandardCategories
from ..util import (
    build_magnet_link,
    urlopen,
)


class Torrentz2Provider(BaseSearchProvider):
    """Search provider for Torrentz2 (general torrents).

    API documentation: https://torrentz2.nz/api
    """

    API_URL = "https://torrentz2.nz/api/v1/search"

    # Category mapping from Torrentz2 API to StandardCategories
    CATEGORY_MAP = {
        2: StandardCategories.MOVIES,  # Movies
        3: StandardCategories.TV,  # TV
        4: StandardCategories.TV_ANIME,  # Anime
        5: StandardCategories.PC,  # Software (default)
        6: StandardCategories.PC_GAMES,  # Games (default)
        7: StandardCategories.AUDIO,  # Music (default)
        8: StandardCategories.AUDIO_AUDIOBOOK,  # AudioBook
        9: StandardCategories.BOOKS,  # Ebook/Course
        10: StandardCategories.XXX,  # XXX
    }

    # Subcategory mapping for categories that have subcategories
    SUBCATEGORY_MAP = {
        1: {  # Other
            1: StandardCategories.AUDIO,  # Audio
            2: StandardCategories.MOVIES,  # Video
            3: StandardCategories.OTHER,  # Image
            4: StandardCategories.BOOKS,  # Document
            5: StandardCategories.PC,  # Program
            6: StandardCategories.PC_MOBILE_ANDROID,  # Android
            7: StandardCategories.PC_ISO,  # DiskImage
            8: StandardCategories.PC,  # Source Code
            9: StandardCategories.PC,  # Database
            11: StandardCategories.OTHER,  # Archive
        },
        5: {  # Software
            1: StandardCategories.PC,  # Windows
            2: StandardCategories.PC_MAC,  # Mac
            3: StandardCategories.PC_MOBILE_ANDROID,  # Android
        },
        6: {  # Games
            1: StandardCategories.PC_GAMES,  # PC
            2: StandardCategories.PC_MAC,  # Mac
            3: StandardCategories.PC_GAMES,  # Linux
            4: StandardCategories.PC_MOBILE_ANDROID,  # Android
        },
        7: {  # Music
            1: StandardCategories.AUDIO_MP3,  # MP3
            2: StandardCategories.AUDIO_LOSSLESS,  # Lossless
            3: StandardCategories.AUDIO,  # Album
            4: StandardCategories.AUDIO_VIDEO,  # Video
        },
    }

    # Category ID to name mapping from Torrentz2 API
    CATEGORY_NAMES = {
        1: "Other",
        2: "Movies",
        3: "TV",
        4: "Anime",
        5: "Softwares",
        6: "Games",
        7: "Music",
        8: "AudioBook",
        9: "Ebook/Course",
        10: "XXX",
    }

    # Subcategory ID to name mapping from Torrentz2 API
    SUBCATEGORY_NAMES = {
        1: {  # Other
            1: "Audio",
            2: "Video",
            3: "Image",
            4: "Document",
            5: "Program",
            6: "Android",
            7: "DiskImage",
            8: "Source Code",
            9: "Database",
            11: "Archive",
        },
        2: {  # Movies
            1: "Dub/Dual Audio",
        },
        4: {  # Anime
            1: "Dub/Dual Audio",
            2: "Subbed",
            3: "Raw",
        },
        5: {  # Softwares
            1: "Windows",
            2: "Mac",
            3: "Android",
        },
        6: {  # Games
            1: "PC",
            2: "Mac",
            3: "Linux",
            4: "Android",
        },
        7: {  # Music
            1: "MP3",
            2: "Lossless",
            3: "Album",
            4: "Video",
        },
    }

    # Reverse mapping from StandardCategories to Torrentz2 category IDs
    STANDARD_TO_TZ2_CATEGORY = {
        StandardCategories.MOVIES: 2,
        StandardCategories.TV: 3,
        StandardCategories.TV_ANIME: 4,
        StandardCategories.PC: 5,
        StandardCategories.PC_GAMES: 6,
        StandardCategories.AUDIO: 7,
        StandardCategories.AUDIO_AUDIOBOOK: 8,
        StandardCategories.BOOKS: 9,
        StandardCategories.XXX: 10,
    }

    # Reverse mapping from StandardCategories to Torrentz2 subcategory IDs
    # Format: {StandardCategory: (category_id, subcategory_id)}
    STANDARD_TO_TZ2_SUBCATEGORY = {
        # Category 1 (Other) subcategories
        StandardCategories.AUDIO: (1, 1),
        StandardCategories.MOVIES: (1, 2),  # Also maps to category 2
        StandardCategories.OTHER: (1, 3),  # Image - prefer this for OTHER
        StandardCategories.BOOKS: (1, 4),  # Also maps to category 9
        StandardCategories.PC: (1, 5),  # Also maps to category 5
        StandardCategories.PC_MOBILE_ANDROID: (1, 6),
        StandardCategories.PC_ISO: (1, 7),
        # Category 5 (Software) subcategories
        StandardCategories.PC_MAC: (5, 2),  # Mac software
        # Category 6 (Games) subcategories - PC_GAMES maps to (6, 1)
        # Category 7 (Music) subcategories
        StandardCategories.AUDIO_MP3: (7, 1),
        StandardCategories.AUDIO_LOSSLESS: (7, 2),
        StandardCategories.AUDIO_VIDEO: (7, 4),
    }

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

        # Convert Standard category IDs to Tz2 category codes
        tz2_category, tz2_sub_category = self._convert_categories_to_tz2(
            categories
        )

        params = {
            "q": query.strip(),
            "limit": 100,  # Max limit (default to 20)
            "sort": "seeders",
        }
        if tz2_category:
            params["category"] = tz2_category
        if tz2_sub_category:
            params["subCategory"] = tz2_sub_category

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

        if "t_category" in result.fields:
            md += f"- **Category:** {result.fields['t_category']}\n"

        if "t_sub_category" in result.fields:
            md += f"- **Subcategory:** {result.fields['t_sub_category']}\n"

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

            cat = torrent.get("category")
            sub_cat = torrent.get("subCategory")

            category = self.get_category(cat, sub_cat)

            # Build provider-specific fields
            fields = {}

            tid = torrent.get("id")

            fields["torrent_id"] = tid
            fields["verified"] = torrent.get("verified")

            if cat:
                fields["t_category"] = self.get_tz2_category(cat)
            if sub_cat:
                fields["t_sub_category"] = self.get_tz2_subcategory(
                    cat, sub_cat
                )

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

    def get_category(
        self, cat: int | None, sub_cat: int | None
    ) -> Category | None:
        """Map Torrentz2 category and subcategory IDs to StandardCategories."""

        if cat is None:
            return None

        # Check if category has subcategories and subcategory is provided
        if cat in self.SUBCATEGORY_MAP and sub_cat is not None:
            category = self.SUBCATEGORY_MAP[cat].get(sub_cat)
            if category:
                return category

        # For category 1 (Other), fallback to OTHER if subcategory not found
        if cat == 1:
            return StandardCategories.OTHER

        # Use main category mapping
        return self.CATEGORY_MAP.get(cat)

    def get_tz2_category(self, cat: int) -> str | None:
        """Get Torrentz2 category name by category ID."""
        return self.CATEGORY_NAMES.get(cat)

    def get_tz2_subcategory(self, cat: int, sub_cat: int) -> str | None:
        """Get Torrentz2 subcategory name by category and subcategory ID."""
        if cat in self.SUBCATEGORY_NAMES:
            return self.SUBCATEGORY_NAMES[cat].get(sub_cat)
        return None

    def _convert_categories_to_tz2(
        self, categories: list[Category] | None
    ) -> tuple[int | None, int | None]:
        """Convert StandardCategories to Torrentz2 category and subcategory IDs.

        Returns:
            tuple[int | None, int | None]: (category_id, subcategory_id)
            Returns (None, None) if no mapping found.
        """
        if not categories:
            return None, None

        # Try to find the most specific mapping first (subcategory)
        for category in categories:
            if category in self.STANDARD_TO_TZ2_SUBCATEGORY:
                cat_id, sub_cat_id = self.STANDARD_TO_TZ2_SUBCATEGORY[category]
                if sub_cat_id:
                    return cat_id, sub_cat_id

        # Fall back to main category mapping
        for category in categories:
            if category in self.STANDARD_TO_TZ2_CATEGORY:
                cat_id = self.STANDARD_TO_TZ2_CATEGORY[category]
                return cat_id, None

        # No mapping found
        return None, None
