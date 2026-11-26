# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bitsearch torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
from typing import Any

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import (
    Category,
    DetailsLink,
    DetailsSection,
    SearchResult,
    StandardCategories,
)
from ..util import (
    build_magnet_link,
    format_files,
    local_time,
    parse_iso_date,
    read_response,
)

logger = get_logger()


class BitsearchProvider(BaseSearchProvider):
    """Search provider for Bitsearch (general torrents).

    API documentation: https://bitsearch.eu/api
    API is limited to 200 requests per day per IP address.
    """

    API_URL = "https://bitsearch.eu/api/v1/search"
    DETAILS_URL = "https://bitsearch.eu/api/v1/torrent"
    SITE_URL = "https://bitsearch.eu"

    # Category mapping from Bitsearch API to StandardCategories
    CATEGORY_MAP = {
        1: StandardCategories.OTHER,  # Other
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

    # Max number of category requests per search, to save API rate limit.
    # Larger selections are searched in all categories at once.
    MAX_CATEGORY_REQUESTS = 3

    # Bitsearch categories containing results of StandardCategories parent.
    # Results from "Other" subcategories (e.g. Other/Video for Movies) are
    # not included.
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
        except urllib.error.HTTPError as e:
            raise Exception(f"API error: {self._error_message(e)}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {e}")

        if not isinstance(data, dict) or not data.get("success"):
            message = data.get("message") if isinstance(data, dict) else None
            raise Exception(f"API error: {message or 'unknown error'}")

        torrents = data.get("results")
        if not isinstance(torrents, list):
            raise Exception("Failed to parse API response: invalid results")

        return [r for t in torrents if (r := self._parse_torrent(t))]

    def _error_message(self, error: urllib.error.HTTPError) -> str:
        """Get error message from API error response.

        For exceeded rate limit, time of its reset is added.
        """
        try:
            message = json.loads(error.read().decode("utf-8")).get("message")
        except (OSError, ValueError, AttributeError):
            message = None
        message = f"HTTP {error.code}: {message or error.reason}"

        reset = parse_iso_date((error.headers or {}).get("X-RateLimit-Reset"))
        if error.code == 429 and reset:
            message += f" (resets at {local_time(reset):%Y-%m-%d %H:%M})"
        return message

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if not result.extra:
            return []

        info: list[tuple[str, str | DetailsLink]] = []

        if "t_category" in result.extra:
            info.append(("Category", result.extra["t_category"]))

        if "t_sub_category" in result.extra:
            info.append(("Subcategory", result.extra["t_sub_category"]))

        if "verified" in result.extra:
            verified = "Yes" if result.extra["verified"] else "No"
            info.append(("Verified", verified))

        details = self._fetch_details(result.extra.get("torrent_id"))
        if not details:
            return [DetailsSection("Information", fields=tuple(info))]

        info.extend(self._format_details(details))
        return [
            DetailsSection("Information", fields=tuple(info)),
            *format_files(details.get("files"), ("path",), "size"),
            *self._format_trackers(details.get("trackers")),
        ]

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

    def _format_details(self, details: dict[str, Any]) -> list[tuple[str, str]]:
        """Format information fields from torrent details."""
        fields = []

        downloads = details.get("downloads")
        if isinstance(downloads, int) and downloads > 0:
            fields.append(("Downloads", str(downloads)))

        tags = details.get("tags")
        if tags and isinstance(tags, list):
            fields.append(("Tags", ", ".join(str(t) for t in tags)))

        return fields

    def _format_trackers(self, trackers: Any) -> list[DetailsSection]:
        """Format trackers section."""
        if not trackers or not isinstance(trackers, list):
            return []

        # "DHT" is listed as tracker, but it isn't URL
        urls = [t for t in trackers if isinstance(t, str) and t != "DHT"]
        if not urls:
            return []
        return [DetailsSection("Trackers", items=tuple(urls))]

    def _parse_torrent(self, torrent: Any) -> SearchResult | None:
        """Parse torrent from search results."""
        if not isinstance(torrent, dict):
            return None

        try:
            title = torrent.get("title")
            if not title:
                return None

            info_hash = parse_info_hash(torrent.get("infohash"))
            if not info_hash:
                return None

            tid = torrent.get("id")
            if not tid:
                return None

            cat = torrent.get("category")
            sub_cat = torrent.get("subCategory")

            category = self._get_category(cat, sub_cat)

            # Build provider-specific fields
            fields: dict[str, Any] = {"torrent_id": tid}

            if isinstance(torrent.get("verified"), bool):
                fields["verified"] = torrent["verified"]

            cat_name = self.CATEGORY_NAMES.get(cat)
            if cat_name:
                fields["t_category"] = cat_name
            sub_cat_name = self.SUBCATEGORY_NAMES.get(cat, {}).get(sub_cat)
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
                categories=(category,) if category else (),
                seeders=parse_count(torrent.get("seeders")),
                leechers=parse_count(torrent.get("leechers")),
                # Search always returns 0 downloads, real count is
                # available in details only
                downloads=None,
                size=parse_count(torrent.get("size")),
                files_count=None,
                upload_date=local_time(
                    parse_iso_date(torrent.get("createdAt"))
                ),
                page_url=(
                    f"{self.SITE_URL}/torrent/{urllib.parse.quote(str(tid))}"
                ),
                freeleech=True,  # Public tracker
                extra=fields,
            )

        except Exception:
            logger.exception(
                "Bitsearch: skipping invalid search result "
                f"{torrent.get('infohash')!r}"
            )
            return None

    def _get_category(self, cat: Any, sub_cat: Any) -> Category | None:
        """Map Bitsearch category and subcategory IDs to StandardCategories."""
        return self.SUBCATEGORY_MAP.get(cat, {}).get(
            sub_cat
        ) or self.CATEGORY_MAP.get(cat)

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
