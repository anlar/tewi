"""Bitsearch torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any

from ...ui.util import print_size
from ...util.log import get_logger, log_time
from ...util.misc import parse_count
from ..base import BaseSearchProvider
from ..models import Category, SearchResult, StandardCategories
from ..util import build_magnet_link, escape_markdown, read_response

logger = get_logger()


class BitsearchProvider(BaseSearchProvider):
    """Search provider for Bitsearch (general torrents).

    API documentation: https://bitsearch.eu/api
    """

    API_URL = "https://bitsearch.eu/api/v1/search"
    DETAILS_URL = "https://bitsearch.eu/api/v1/torrent"
    SITE_URL = "https://bitsearch.eu"

    # Max number of files listed in details
    MAX_DETAILS_FILES = 100

    # Category mapping from Bitsearch API to StandardCategories
    CATEGORY_MAP = {
        2: StandardCategories.MOVIES,  # Movies
        3: StandardCategories.TV,  # TV
        4: StandardCategories.TV_ANIME,  # Anime
        5: StandardCategories.PC,  # Software (default)
        6: StandardCategories.PC_GAMES,  # Games (default)
        7: StandardCategories.AUDIO,  # Music (default)
        8: StandardCategories.AUDIO_AUDIOBOOK,  # AudioBook
        9: StandardCategories.BOOKS,  # Ebook/Course (default)
        10: StandardCategories.XXX,  # XXX (default)
    }

    # Subcategory mapping, for subcategories more specific than category
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
            19: StandardCategories.PC,  # Firmware
        },
        2: {  # Movies
            2: StandardCategories.MOVIES_UHD,  # 4K/UHD
            3: StandardCategories.MOVIES_BLURAY,  # BluRay
            4: StandardCategories.MOVIES_WEBDL,  # WEB-DL/WebRip
            5: StandardCategories.MOVIES_DVD,  # DVD
        },
        3: {  # TV
            5: StandardCategories.TV_DOCUMENTARY,  # Documentary
            6: StandardCategories.TV_SPORT,  # Sports
        },
        5: {  # Software
            2: StandardCategories.PC_MAC,  # Mac
            3: StandardCategories.PC_MOBILE_ANDROID,  # Android
            5: StandardCategories.PC_MOBILE_IOS,  # iOS
        },
        6: {  # Games
            2: StandardCategories.PC_MAC,  # Mac
            4: StandardCategories.PC_MOBILE_ANDROID,  # Android
            5: StandardCategories.CONSOLE,  # PlayStation
            6: StandardCategories.CONSOLE,  # Xbox
            7: StandardCategories.CONSOLE,  # Nintendo
            8: StandardCategories.PC_MOBILE_IOS,  # iOS
        },
        7: {  # Music
            1: StandardCategories.AUDIO_MP3,  # MP3
            2: StandardCategories.AUDIO_LOSSLESS,  # Lossless
            4: StandardCategories.AUDIO_VIDEO,  # Video
        },
        9: {  # Ebook/Course
            1: StandardCategories.BOOKS_EBOOK,  # Ebook
            2: StandardCategories.BOOKS_TECHNICAL,  # Course/Tutorial
            3: StandardCategories.BOOKS_COMICS,  # Comics/Manga
            4: StandardCategories.BOOKS_MAGS,  # Magazine
            6: StandardCategories.BOOKS_MAGS,  # Newspaper
        },
        10: {  # XXX
            2: StandardCategories.XXX_IMAGESET,  # Images
        },
    }

    # Category ID to name mapping, from /api/v1/categories
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

    # Subcategory ID to name mapping, from /api/v1/categories
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
            10: "Dataset",
            11: "Archive",
            16: "Fonts",
            17: "3D/CAD",
            18: "Subtitles",
            19: "Firmware",
        },
        2: {  # Movies
            1: "Dub/Dual Audio",
            2: "4K/UHD",
            3: "BluRay",
            4: "WEB-DL/WebRip",
            5: "DVD",
            6: "CAM/TS",
            7: "Documentary",
            8: "Animation",
            9: "Lossless/Remux",
        },
        3: {  # TV
            1: "Episode",
            2: "Season Pack",
            3: "Complete Series",
            4: "Reality",
            5: "Documentary",
            6: "Sports",
            7: "Kids",
        },
        4: {  # Anime
            1: "Dub/Dual Audio",
            2: "Subbed",
            3: "Raw",
            4: "Movie",
            5: "Series/Season",
            6: "OVA/ONA",
            7: "Action",
            8: "Adventure",
            9: "Comedy",
            10: "Drama",
            11: "Fantasy",
            12: "Sci-Fi",
            13: "Romance",
            14: "Horror",
            15: "Slice of Life",
            16: "Sports",
            17: "Mecha",
            18: "Mystery",
            19: "Isekai",
        },
        5: {  # Softwares
            1: "Windows",
            2: "Mac",
            3: "Android",
            4: "Linux",
            5: "iOS",
            6: "Drivers/Firmware",
            7: "Plugins/Add-ons",
            8: "Security/Antivirus",
        },
        6: {  # Games
            1: "PC",
            2: "Mac",
            3: "Linux",
            4: "Android",
            5: "PlayStation",
            6: "Xbox",
            7: "Nintendo",
            8: "iOS",
            9: "Retro/Emulation",
            10: "VR",
        },
        7: {  # Music
            1: "MP3",
            2: "Lossless",
            3: "Album",
            4: "Video",
            5: "Single/EP",
            6: "Discography",
            7: "Soundtrack",
            8: "Live/Concert",
        },
        8: {  # AudioBook
            1: "Fiction",
            2: "Non-Fiction",
            3: "Educational",
            4: "Audio Drama",
            5: "Language Learning",
        },
        9: {  # Ebook/Course
            1: "Ebook",
            2: "Course/Tutorial",
            3: "Comics/Manga",
            4: "Magazine",
            5: "Academic/Research",
            6: "Newspaper",
        },
        10: {  # XXX
            1: "Video",
            2: "Images",
            3: "Games",
            4: "VR",
            5: "Animation",
            6: "Amateur",
            7: "Studio",
            8: "Compilation",
            9: "Solo",
            10: "Couples",
        },
    }

    # Bitsearch categories containing results of StandardCategories parent.
    # Results from "Other" subcategories (e.g. Other/Video for Movies) are
    # not included.
    # Max number of category requests per search, to save API rate limit.
    # Larger selections are searched in all categories at once.
    MAX_CATEGORY_REQUESTS = 3

    PARENT_TO_BS_CATEGORIES = {
        StandardCategories.CONSOLE: {6},
        StandardCategories.MOVIES: {2},
        StandardCategories.AUDIO: {7, 8},
        StandardCategories.PC: {5, 6},
        StandardCategories.TV: {3, 4},
        StandardCategories.XXX: {10},
        StandardCategories.BOOKS: {9},
        StandardCategories.OTHER: {1},
    }

    @property
    def id(self) -> str:
        return "bitsearch"

    @property
    def name(self) -> str:
        return "Bitsearch"

    @property
    def short_name(self) -> str:
        return "BITS"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        if not query or not query.strip():
            return []

        # API filters by single category, so request each category
        # separately; None requests all categories
        bs_categories = self._convert_categories_to_bs(categories) or [None]

        results = []
        for bs_category in bs_categories:
            results.extend(self._search_category(query.strip(), bs_category))
        return results

    def _search_category(
        self, query: str, bs_category: int | None
    ) -> list[SearchResult]:
        """Search torrents in single Bitsearch category.

        Args:
            query: Search query
            bs_category: Bitsearch category ID, or None for all categories

        Returns:
            Parsed search results
        """
        params = {
            "q": query,
            "limit": 100,  # Max limit (default to 20)
            "sort": "seeders",
        }
        if bs_category:
            params["category"] = bs_category

        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        if not data.get("success"):
            return []

        results = []
        for torrent in data.get("results") or []:
            result = self._parse_torrent(torrent)
            if result:
                results.append(result)
        return results

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

        details = self._fetch_details(result.fields.get("torrent_id"))
        if details:
            md += self._format_details(details)

        return md

    @log_time
    def _fetch_details(self, torrent_id: str | None) -> dict[str, Any] | None:
        """Fetch torrent details (files, trackers, tags) from API.

        Args:
            torrent_id: Bitsearch torrent ID

        Returns:
            Torrent details, or None if they could not be loaded
        """
        if not torrent_id:
            return None

        url = f"{self.DETAILS_URL}/{urllib.parse.quote(str(torrent_id))}"

        try:
            with self.urlopen(url) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except (OSError, ValueError) as e:
            logger.warning(f"Bitsearch: failed to fetch details: {e}")
            return None

        if not isinstance(data, dict) or not data.get("success"):
            return None

        torrent = data.get("torrent")
        return torrent if isinstance(torrent, dict) else None

    def _format_details(self, details: dict[str, Any]) -> str:
        """Format torrent details as Markdown sections."""
        md = ""

        downloads = details.get("downloads")
        if isinstance(downloads, int) and downloads > 0:
            md += f"- **Downloads:** {downloads}\n"

        tags = details.get("tags")
        if tags and isinstance(tags, list):
            tags_str = ", ".join(escape_markdown(t) for t in tags)
            md += f"- **Tags:** {tags_str}\n"

        md += self._format_files(details.get("files"))
        md += self._format_trackers(details.get("trackers"))
        return md

    def _format_files(self, files: Any) -> str:
        """Format files section, limited to MAX_DETAILS_FILES entries."""
        if not files or not isinstance(files, list):
            return ""

        md = f"\n## Files ({len(files)})\n"
        for f in files[: self.MAX_DETAILS_FILES]:
            if not isinstance(f, dict) or not f.get("path"):
                continue
            md += f"- {escape_markdown(f['path'])}"
            if isinstance(f.get("size"), int):
                md += f" ({print_size(f['size'])})"
            md += "\n"

        if len(files) > self.MAX_DETAILS_FILES:
            more = len(files) - self.MAX_DETAILS_FILES
            md += f"- ...and {more} more\n"
        return md

    def _format_trackers(self, trackers: Any) -> str:
        """Format trackers section."""
        if not trackers or not isinstance(trackers, list):
            return ""

        # "DHT" is listed as tracker, but it isn't URL
        urls = [t for t in trackers if isinstance(t, str) and t != "DHT"]
        if not urls:
            return ""
        return "\n## Trackers\n" + "".join(
            f"- {escape_markdown(t)}\n" for t in urls
        )

    def _parse_torrent(self, torrent: dict[str, Any]) -> SearchResult | None:
        try:
            title = torrent.get("title")
            if not title:
                return None

            info_hash = torrent.get("infohash")
            if not info_hash:
                return None

            tid = torrent.get("id")
            if not tid:
                return None

            cat = torrent.get("category")
            sub_cat = torrent.get("subCategory")

            category = self.get_category(cat, sub_cat)

            # Build provider-specific fields
            fields = {}

            fields["torrent_id"] = tid
            fields["verified"] = torrent.get("verified")

            if cat:
                fields["t_category"] = self.get_bs_category(cat)
            sub_cat_name = self.get_bs_subcategory(cat, sub_cat)
            if sub_cat_name:
                fields["t_sub_category"] = sub_cat_name

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=build_magnet_link(info_hash=info_hash, name=title),
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=[category] if category else None,
                seeders=parse_count(torrent.get("seeders")),
                leechers=parse_count(torrent.get("leechers")),
                # Search always returns 0 downloads, real count is
                # available in details only
                downloads=None,
                size=parse_count(torrent.get("size")),
                files_count=None,
                upload_date=self._parse_date(torrent.get("createdAt")),
                page_url=(
                    f"{self.SITE_URL}/torrent/{urllib.parse.quote(str(tid))}"
                ),
                freeleech=True,  # Public tracker
                fields=fields,
            )

        except (KeyError, ValueError, TypeError):
            return None

    def _parse_date(self, value: str | None) -> datetime | None:
        """Parse ISO 8601 date string returned by API."""
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def get_category(
        self, cat: int | None, sub_cat: int | None
    ) -> Category | None:
        """Map Bitsearch category and subcategory IDs to StandardCategories."""

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

    def get_bs_category(self, cat: int) -> str | None:
        """Get Bitsearch category name by category ID."""
        return self.CATEGORY_NAMES.get(cat)

    def get_bs_subcategory(self, cat: int, sub_cat: int) -> str | None:
        """Get Bitsearch subcategory name by category and subcategory ID."""
        if cat in self.SUBCATEGORY_NAMES:
            return self.SUBCATEGORY_NAMES[cat].get(sub_cat)
        return None

    def _convert_categories_to_bs(
        self, categories: list[Category] | None
    ) -> list[int]:
        """Convert StandardCategories to Bitsearch categories to search.

        Args:
            categories: Selected categories

        Returns:
            Sorted Bitsearch category IDs, or empty list to search all
            categories (also when there are too many to search separately)
        """
        if not categories:
            return []

        bs_categories: set[int] = set()
        for category in categories:
            parent = category.parent or category
            bs_ids = self.PARENT_TO_BS_CATEGORIES.get(parent)
            if not bs_ids:
                return []
            bs_categories |= bs_ids

        if len(bs_categories) > self.MAX_CATEGORY_REQUESTS:
            return []
        return sorted(bs_categories)
