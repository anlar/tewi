# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Jackett torrent search provider implementation."""

import json
import re
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

from ...util.log import get_logger, log_time
from ...util.misc import parse_count, parse_info_hash
from ..base import BaseSearchProvider
from ..models import (
    Category,
    DetailsLink,
    DetailsSection,
    Indexer,
    SearchResult,
    StandardCategories,
)
from ..util import (
    MAX_ERROR_BODY_SIZE,
    build_magnet_link,
    details_value,
    format_description,
    local_time,
    read_response,
)

logger = get_logger()


class JackettProvider(BaseSearchProvider):
    """Search provider for Jackett (meta-indexer).

    Jackett provides unified access to multiple torrent indexers
    through a single API. Requires local Jackett instance.
    Documentation: https://github.com/Jackett/Jackett
    """

    # Indexer search status in results (ManualSearchResultIndexerStatus)
    INDEXER_OK = 2

    _API_KEY_RE = re.compile(r"([?&]apikey=)[^&]*")

    def __init__(
        self,
        jackett_url: str | None = None,
        api_key: str | None = None,
        multi_indexer: bool = False,
        timeout: int | None = None,
    ):
        """Initialize Jackett provider with configuration.

        Args:
            jackett_url: Base URL of Jackett instance
            api_key: API key for Jackett authentication
            multi_indexer: If True, load all indexers individually.
                          If False, use single "all" endpoint (default)
            timeout: Default timeout in seconds for search requests
        """
        super().__init__(timeout)
        self.jackett_url: str | None = jackett_url
        self.api_key: str | None = api_key
        self.multi_indexer: bool = multi_indexer
        self._config_error: str | None = self._validate_config(
            jackett_url, api_key
        )
        self._cached_indexers: list[Indexer] | None = None
        self._cache_time: datetime | None = None
        self._cache_duration: timedelta = timedelta(minutes=10)

    @property
    def id(self) -> str:
        return "jackett"

    @property
    def name(self) -> str:
        return "Jackett"

    def indexers(self) -> list[Indexer]:
        """Return list of configured indexers from Jackett instance.

        When multi_indexer is False, returns a single "Jackett" indexer
        that searches all indexers via the /all endpoint.

        When multi_indexer is True, fetches and returns all individual
        indexers. Uses a 10-minute cache to avoid repeated API calls.

        Returns:
            List of (indexer_id, indexer_name) tuples from Jackett,
            or empty list if not configured or error occurs
        """
        if self._config_error:
            logger.debug(f"Jackett not configured: {self._config_error}")
            return []

        # If multi_indexer is disabled, return single "Jackett" indexer
        if not self.multi_indexer:
            logger.debug("Jackett: multi_indexer disabled, returning single")
            return [Indexer(id="jackett:all", name="Jackett")]

        # Check if cache is valid
        if self._is_cache_valid():
            logger.debug("Jackett: returning cached indexers")
            return self._cached_indexers

        try:
            url = self._build_indexers_url()
            data = self._fetch_indexers(url)
            indexers = self._process_indexers(data)
            logger.info(f"Jackett: loaded {len(indexers)} indexers")

            # Update cache
            self._cached_indexers = indexers
            self._cache_time = datetime.now()

            return indexers
        except Exception as e:
            # Return empty list if indexers cannot be fetched
            logger.warning(f"Failed to load Jackett indexers: {e}")
            return []

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search Jackett for torrents across all indexers.

        Args:
            query: Search term
            categories: Category IDs to filter by (optional)
            indexers: Indexer IDs to search (optional - if None, search all)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails, all indexers failed or not
                configured
        """
        if self._config_error:
            raise Exception(self._config_error)

        if not query or not query.strip():
            return []

        # Without multi_indexer, single "all" indexer is selected
        if not self.multi_indexer or (indexers and "all" in indexers):
            indexers = None

        url = self._build_search_url(query, categories, indexers)
        data = self._fetch_results(url)
        return self._process_results(data)

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate Jackett-specific details for right column.

        Prints all provider-specific fields from the search result.
        Applies transformations to enhance certain fields (e.g., IMDB).

        Args:
            result: Search result to format

        Returns:
            Sections with Jackett details
        """
        if not result.extra:
            return []

        # All fields in sorted order for consistent display
        fields = [
            self._transform_field(key, result.extra[key])
            for key in sorted(result.extra.keys())
            if key != "Description"
        ]
        sections = [DetailsSection("Indexer Info", fields=tuple(fields))]

        # Long text is shown as paragraph, not squeezed into field value
        if "Description" in result.extra:
            sections.append(
                DetailsSection("Description", text=result.extra["Description"])
            )
        return sections

    def _validate_config(
        self, jackett_url: str | None, api_key: str | None
    ) -> str | None:
        """Validate configuration and return error message if invalid.

        Args:
            jackett_url: Base URL of Jackett instance
            api_key: API key for Jackett authentication

        Returns:
            Error message string if invalid, None if valid
        """
        if not jackett_url or not jackett_url.strip():
            return (
                "Jackett URL not configured. "
                "Set jackett_url in [search] section."
            )
        if not api_key or not api_key.strip():
            return (
                "Jackett API key not configured. "
                "Set jackett_api_key in [search] section."
            )
        return None

    def _is_cache_valid(self) -> bool:
        """Check if cached indexers are still valid.

        Returns:
            True if cache exists and hasn't expired, False otherwise
        """
        if self._cached_indexers is None or self._cache_time is None:
            return False

        time_elapsed = datetime.now() - self._cache_time
        return time_elapsed < self._cache_duration

    def _build_indexers_url(self) -> str:
        """List configured indexers without querying any tracker sites."""
        base_url = self.jackett_url.rstrip("/")
        endpoint = f"{base_url}/api/v2.0/indexers/all/results/torznab/api"
        params = {
            "apikey": self.api_key,
            "t": "indexers",
            "configured": "true",
        }
        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    def _fetch_indexers(self, url: str) -> ET.Element:
        """Fetch and parse the Torznab indexer metadata from Jackett.

        Args:
            url: Complete API URL

        Returns:
            Parsed XML indexers element

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            with self.urlopen(url, timeout=10) as response:
                # ElementTree doesn't load external entities or DTDs, and
                # expat (>= 2.4.1) limits entity expansion
                return ET.fromstring(read_response(response))  # noqa: S314
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Exception("Invalid Jackett API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Jackett at {self.jackett_url}: {e.reason}"
            )
        except ET.ParseError as e:
            raise Exception(f"Failed to parse Jackett indexers XML: {e}")

    def _process_indexers(self, data: ET.Element) -> list[Indexer]:
        """Process configured indexers from the metadata response.

        Args:
            data: Parsed XML data from the indexer-list command

        Returns:
            List of Indexer objects
        """
        # Jackett reports Torznab errors (e.g. invalid API key) with HTTP 200
        if data.tag == "error":
            raise ValueError(
                data.get("description") or "Jackett returned an error"
            )
        if data.tag != "indexers":
            raise ValueError("Unexpected Jackett indexer metadata response")

        indexers = []
        for indexer in data.findall("indexer"):
            if indexer.get("configured") != "true":
                continue
            indexer_id = indexer.get("id")
            indexer_name = (indexer.findtext("title") or "").strip()
            # Only include indexers with valid ID and Name
            if indexer_id and indexer_name:
                # Prefix with jackett: to distinguish from other providers
                full_id = f"jackett:{indexer_id}"
                indexers.append(
                    Indexer(
                        full_id,
                        indexer_name,
                        "Jackett",
                    )
                )
        return sorted(indexers, key=lambda indexer: indexer.name.lower())

    def _build_search_url(
        self,
        query: str,
        categories: list[Category] | None,
        indexers: list[str] | None,
    ) -> str:
        """Build Jackett API search URL.

        Args:
            query: Search term
            categories: Categories to filter by (optional)
            indexers: Indexer IDs to search, or None for all

        Returns:
            Complete URL with parameters
        """
        base_url = self.jackett_url.rstrip("/")
        endpoint = f"{base_url}/api/v2.0/indexers/all/results"
        params = [("apikey", self.api_key), ("Query", query.strip())]

        # Jackett binds repeated parameter to category list, while single
        # comma-separated value is ignored
        params += [("Category", str(c.id)) for c in categories or []]

        # Jackett splits comma-separated indexer IDs
        if indexers:
            params.append(("Tracker[]", ",".join(indexers)))

        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    def _fetch_results(self, url: str) -> dict:
        """Fetch and parse JSON results from Jackett API.

        Args:
            url: Complete API URL

        Returns:
            Parsed JSON data

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            # API key is accepted only in URL query, so it's not logged
            masked_url = self._API_KEY_RE.sub(r"\1***", url)
            logger.debug(f"Jackett: requesting URL: {masked_url}")
            with self.urlopen(url) as response:
                return json.loads(read_response(response).decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ""
            try:
                if e.fp:
                    error_body = e.fp.read(MAX_ERROR_BODY_SIZE).decode(
                        "utf-8", errors="replace"
                    )
                    logger.error(
                        f"Jackett HTTP {e.code} response: {error_body}"
                    )
            except Exception:
                pass
            if e.code in (401, 403):
                raise Exception("Invalid Jackett API key")
            raise Exception(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Jackett at {self.jackett_url}: {e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Jackett response: {e}")

    def _process_results(self, data: Any) -> list[SearchResult]:
        """Process API response and convert to SearchResult list.

        Args:
            data: Parsed JSON response

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If response is invalid or all indexers failed
        """
        results = data.get("Results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            raise Exception("Failed to parse Jackett response: no results")

        self._check_indexers(data.get("Indexers"), has_results=bool(results))
        return [r for d in results if (r := self._parse_result(d))]

    def _check_indexers(self, indexers: Any, has_results: bool) -> None:
        """Log indexers that failed to search.

        Args:
            indexers: Indexers search status from Jackett response
            has_results: Whether any indexer returned results

        Raises:
            Exception: If all indexers failed
        """
        if not isinstance(indexers, list):
            return

        failed = []
        for indexer in indexers:
            if not isinstance(indexer, dict):
                continue
            if indexer.get("Status") in (self.INDEXER_OK, "OK"):
                continue
            # Error is exception text with stack trace
            lines = str(indexer.get("Error") or "").strip().splitlines()
            error = lines[0] if lines else "unknown error"
            failed.append(
                f"{indexer.get('Name') or indexer.get('ID')}: {error}"
            )

        for error in failed:
            logger.warning(f"Jackett indexer failed: {error}")

        if failed and len(failed) == len(indexers) and not has_results:
            raise Exception(f"All indexers failed ({'; '.join(failed)})")

    def _parse_result(self, result: Any) -> SearchResult | None:
        """Parse a single result from Jackett API response.

        Args:
            result: Single result dict from Jackett API

        Returns:
            SearchResult or None if parsing fails
        """
        if not isinstance(result, dict):
            return None

        try:
            title = result.get("Title")
            if not title:
                return None

            info_hash = parse_info_hash(result.get("InfoHash"))

            # Extract both link types
            magnet_link = self._extract_magnet_link(title, info_hash, result)
            torrent_link = result.get("Link")

            # Skip result only if we have NEITHER link type
            if not magnet_link and not torrent_link:
                return None

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=torrent_link,
                provider=self._build_provider_name(result),
                provider_short=self._build_provider_name(result, short=True),
                provider_source="J",
                provider_id=self.id,
                categories=tuple(self._map_jackett_category(result) or ()),
                seeders=parse_count(result.get("Seeders")),
                # Search results API reports leechers as peers
                leechers=parse_count(result.get("Peers")),
                downloads=parse_count(result.get("Grabs")),
                size=parse_count(result.get("Size")),
                files_count=parse_count(result.get("Files")),
                upload_date=local_time(self._parse_upload_date(result)),
                page_url=result.get("Details"),
                freeleech=result.get("DownloadVolumeFactor") == 0,
                extra=self._build_fields(result),
            )
        except Exception:
            logger.exception(
                "Jackett: skipping invalid search result "
                f"{result.get('Title')!r}"
            )
            return None

    def _extract_magnet_link(
        self, title: str, info_hash: str | None, result: dict[str, Any]
    ) -> str | None:
        """Extract or generate magnet link from result.

        Priority: MagnetUri field → Generated from InfoHash → None

        Args:
            title: Torrent title (to add to generated magnet link)
            info_hash: Torrent info hash (may be None)
            result: Result dict from Jackett API

        Returns:
            Magnet URI string or None if unavailable
        """
        magnet_uri = result.get("MagnetUri")
        if magnet_uri:
            return magnet_uri

        # Generate magnet from info hash if available
        if info_hash:
            return build_magnet_link(info_hash=info_hash, name=title)

        return None

    def _parse_upload_date(self, result: dict[str, Any]) -> datetime | None:
        """Parse upload date from result.

        Args:
            result: Result dict from Jackett API

        Returns:
            datetime object or None if parsing fails
        """
        publish_date = result.get("PublishDate")
        if not publish_date:
            return None

        try:
            return datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _build_provider_name(
        self, result: dict[str, Any], short: bool = False
    ) -> str:
        """Build provider name from tracker name.

        Args:
            result: Result dict from Jackett API
            short: Truncate name for compact view

        Returns:
            Provider name string (plain text)
        """
        tracker = str(
            result.get("Tracker") or result.get("TrackerId") or "Unknown"
        )
        return tracker[:5] if short else tracker

    def _build_fields(self, result: dict[str, Any]) -> dict[str, object]:
        """Build provider-specific fields dict.

        Includes all fields from Jackett response except:
        - null/empty fields
        - fields already mapped to SearchResult main attributes

        Args:
            result: Result dict from Jackett API

        Returns:
            Dictionary of provider-specific fields
        """
        # Fields already mapped to SearchResult attributes
        excluded_fields = {
            "Title",  # -> title
            "Category",  # -> category (via _map_jackett_category)
            "CategoryDesc",  # -> category
            "Seeders",  # -> seeders
            "Peers",  # -> leechers
            "Grabs",  # -> downloads
            "Size",  # -> size
            "Files",  # -> files_count
            "MagnetUri",  # -> magnet_link
            "InfoHash",  # -> info_hash
            "PublishDate",  # -> upload_date
            "Tracker",  # -> provider (via _build_provider_name)
            "TrackerId",  # -> provider (via _build_provider_name)
            "Details",  # -> page_url
            "Comments",  # old Jackett name of Details
            "Link",  # -> torrent_link
            "Guid",  # ignore
            "FirstSeen",  # ignore
            "DownloadVolumeFactor",  # -> freeleech
            "UploadVolumeFactor",  # always 1 for public trackers
            "Gain",  # Jackett UI sorting value
            "Description",  # added as text below
            # Jackett proxy links contain API key
            "Poster",
            "BlackholeLink",
        }

        fields = {}
        for key, value in result.items():
            # Skip excluded fields
            if key in excluded_fields:
                continue

            # Skip null/empty values
            if value is None or value == "" or value == []:
                continue

            if isinstance(value, list):
                fields[key] = ", ".join(str(v) for v in value)
            else:
                fields[key] = str(value)

        # Some indexers return HTML description
        description = format_description(
            result.get("Description"), result.get("Title")
        )
        if description:
            fields["Description"] = description

        return fields

    def _map_jackett_category(
        self, result: dict[str, Any]
    ) -> list[Category] | None:
        """Map Jackett category codes to Category objects.

        Jackett uses Torznab category IDs with hierarchy:
        - Parent categories end in 000 (e.g., 2000 = Movies)
        - Subcategories have specific IDs (e.g., 2040 = Movies/HD)

        Args:
            result: Result dict from Jackett API

        Returns:
            List of Category objects (may contain parent and subcategory)
        """
        category_codes = result.get("Category")
        if not category_codes:
            return None

        # Get all category codes from the result
        codes = self._extract_category_codes(category_codes)
        if not codes:
            return None

        # Map codes to Category objects
        categories = []
        for code in codes:
            category = StandardCategories.get_by_id(code)
            if category:
                categories.append(category)

        return categories

    def _extract_category_codes(self, category_codes: Any) -> list[int]:
        """Extract all category codes from Jackett response.

        Args:
            category_codes: Category codes (list or single value)

        Returns:
            List of category codes as integers
        """
        codes = []
        try:
            if isinstance(category_codes, list):
                for code in category_codes:
                    codes.append(int(code))
            else:
                codes.append(int(category_codes))
        except (ValueError, TypeError):
            pass
        return codes

    def _transform_field(
        self, key: str, value: str
    ) -> tuple[str, str | DetailsLink]:
        """Transform field key and value for display.

        Applies transformations like converting IDs to URLs.
        This is a universal mechanism for enhancing field display.

        Args:
            key: Field name from Jackett response
            value: Field value

        Returns:
            Tuple of (display_name, display_value), where value is link
            for HTTP(S) URL
        """
        if key == "Imdb" and value.isdigit() and int(value):
            # IMDB IDs have at least 7 digits
            return "IMDB", DetailsLink(
                f"https://www.imdb.com/title/tt{int(value):07d}/"
            )

        return key, details_value(value)
