"""Bitmagnet torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ...util.log import get_logger, log_time
from ..base import BaseSearchProvider
from ..models import Category, SearchResult, StandardCategories
from ..util import urlopen_post

logger = get_logger()


class BitmagnetProvider(BaseSearchProvider):
    """Search provider for Bitmagnet (self-hosted torrent DHT search).

    Bitmagnet provides access to DHT-crawled torrents via GraphQL API.
    Documentation: https://bitmagnet.io
    Available endpoints: https://bitmagnet.io/guides/endpoints.html
    """

    # GraphQL query template for search with $QUERY placeholder
    GRAPHQL_QUERY = """{
  torrentContent {
    search(
      input: {
        queryString: "$QUERY"
        offset: 0
        limit: 50
        orderBy: { field: seeders, descending: true }
      }
    ) {
      items {
        id
        infoHash
        contentType
        contentSource
        contentId
        title
        languages {
          id
          name
        }
        episodes {
          label
          seasons {
            season
            episodes
          }
        }
        videoResolution
        videoSource
        videoCodec
        video3d
        videoModifier
        releaseGroup
        seeders
        leechers
        publishedAt
        createdAt
        updatedAt
        torrent {
          infoHash
          name
          size
          filesCount
          seeders
          leechers
          magnetUri
          hasFilesInfo
          singleFile
          extension
          fileType
          fileTypes
          filesStatus
          tagNames
          createdAt
          updatedAt
          sources {
            key
            name
            importId
            seeders
            leechers
          }
        }
      }
    }
  }
}"""

    # GraphQL query template for fetching torrent details by info hash
    GRAPHQL_DETAILS_QUERY = """{
  torrentContent {
    search(
      input: {
        queryString: "$INFOHASH"
      }
    ) {
      items {
        infoHash
        content {
          type
          source
          id
          title
          releaseDate
          releaseYear
          adult
          originalLanguage {
            id
            name
          }
          originalTitle
          overview
          runtime
          popularity
          voteAverage
          voteCount
          externalLinks {
            metadataSource {
              key
              name
            }
            url
          }
        }
      }
    }
  }
}"""

    # Mapping of Bitmagnet ContentType enum to StandardCategories
    # Source: https://github.com/bitmagnet-io/bitmagnet/blob/main/internal/protobuf/bitmagnet.proto
    CONTENT_TYPE_CATEGORY_MAP = {
        "movie": StandardCategories.MOVIES,  # 1
        "tv_show": StandardCategories.TV,  # 2
        "music": StandardCategories.AUDIO,  # 3
        "ebook": StandardCategories.BOOKS,  # 4
        "comic": StandardCategories.BOOKS_COMICS,  # 5
        "audiobook": StandardCategories.AUDIO_AUDIOBOOK,  # 6
        "game": StandardCategories.PC,  # 7
        "software": StandardCategories.PC,  # 8
        "xxx": StandardCategories.XXX,  # 9
        # "unknown" (0) -> not in map, returns empty list
    }

    def __init__(self, bitmagnet_url: str | None = None) -> None:
        """Initialize Bitmagnet provider with configuration.

        Args:
            bitmagnet_url: Base URL of Bitmagnet instance
        """
        self.bitmagnet_url: str | None = bitmagnet_url
        self._config_error: str | None = self._validate_config(bitmagnet_url)

    @property
    def id(self) -> str:
        return "bitmagnet"

    @property
    def name(self) -> str:
        return "Bitmagnet"

    @log_time
    def search(
        self,
        query: str,
        categories: list | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search Bitmagnet for torrents via GraphQL API.

        Args:
            query: Search term
            categories: Category objects to filter by (not used by Bitmagnet)
            indexers: Indexer IDs (not used by Bitmagnet)

        Returns:
            List of SearchResult objects

        Raises:
            Exception: If API request fails or not configured
        """
        if self._config_error:
            raise Exception(self._config_error)

        if not query or not query.strip():
            return []

        # Build GraphQL query
        query_body = self._build_graphql_query(query.strip())

        # Fetch results from GraphQL endpoint
        url = f"{self.bitmagnet_url.rstrip('/')}/graphql"
        data = self._fetch_results(url, query_body)

        # Process and return results
        return self._process_results(data)

    def details_extended(self, result: SearchResult) -> str:
        """Generate Bitmagnet-specific details for right column.

        Prints extended metadata from the search result. Attempts to fetch
        additional content details from GraphQL API with 5-second timeout.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with Bitmagnet details
        """
        if not result.fields:
            return ""

        # Try to fetch additional torrent details
        fields = dict(result.fields) if result.fields else {}
        try:
            content_details = self._fetch_content_details(result.info_hash)
            if content_details:
                # Merge additional fields from content details
                fields.update(content_details)
        except Exception as e:
            logger.debug(f"Bitmagnet: failed to fetch content details: {e}")

        sections = [
            self._format_content_section(fields),
            self._format_video_section(fields),
            self._format_release_section(fields),
            self._format_links_section(fields),
            self._format_timestamps_section(fields),
        ]

        return "".join(s for s in sections if s)

    def _format_content_section(self, fields: dict) -> str:
        """Format content metadata section including sources and tags."""
        field_defs = [
            ("content_type", "Content Type"),
            ("content_source", "Content Source"),
            ("content_id", "Content ID"),
            ("content_title", "Title"),
            ("original_title", "Original Title"),
            ("release_year", "Release Year"),
            ("release_date", "Release Date"),
            ("original_language", "Original Language"),
            ("runtime", "Runtime"),
            ("rating", "Rating"),
            ("popularity", "Popularity"),
            ("adult", "Adult"),
            ("overview", "Overview"),
            ("file_types", "File Types"),
            ("tag_names", "Tags"),
            ("sources", "Sources"),
        ]
        return self._format_field_section("Content", fields, field_defs)

    def _format_video_section(self, fields: dict) -> str:
        """Format video metadata section."""
        field_defs = [
            ("video_resolution", "Resolution"),
            ("video_source", "Source"),
            ("video_codec", "Codec"),
            ("video_3d", "3D"),
            ("video_modifier", "Modifier"),
        ]
        return self._format_field_section("Video", fields, field_defs)

    def _format_release_section(self, fields: dict) -> str:
        """Format release metadata section."""
        field_defs = [
            ("release_group", "Release Group"),
            ("languages", "Languages"),
            ("episodes", "Episodes"),
        ]
        return self._format_field_section("Release", fields, field_defs)

    def _format_links_section(self, fields: dict) -> str:
        """Format external links section."""
        links_data = fields.get("external_links")
        if not links_data:
            return ""

        # links_data is a list of tuples: [(name, url), ...]
        if not isinstance(links_data, list):
            return ""

        lines = []
        for name, url in links_data:
            lines.append(f"- **{name}:** {url}\n")

        if lines:
            return "\n## Links\n" + "".join(lines)
        return ""

    def _format_timestamps_section(self, fields: dict) -> str:
        """Format timestamps section."""
        field_defs = [
            ("item_created_at", "Item Created"),
            ("item_updated_at", "Item Updated"),
            ("torrent_created_at", "Torrent Created"),
            ("torrent_updated_at", "Torrent Updated"),
        ]
        return self._format_field_section("Timestamps", fields, field_defs)

    def _format_field_section(
        self,
        title: str,
        fields: dict,
        field_defs: list[tuple[str, str]],
    ) -> str:
        """Format a section with field definitions.

        Args:
            title: Section title
            fields: Field values dict
            field_defs: List of (field_key, field_label) tuples

        Returns:
            Formatted section or empty string
        """
        lines = []
        for field_key, field_label in field_defs:
            value = fields.get(field_key)
            if value:
                lines.append(f"- **{field_label}:** {value}\n")

        if lines:
            prefix = "\n" if title != "Content" else ""
            return f"{prefix}## {title}\n" + "".join(lines)
        return ""

    def _validate_config(self, bitmagnet_url: str | None) -> str | None:
        """Validate configuration and return error message if invalid.

        Args:
            bitmagnet_url: Base URL of Bitmagnet instance

        Returns:
            Error message string if invalid, None if valid
        """
        if not bitmagnet_url or not bitmagnet_url.strip():
            return (
                "Bitmagnet URL not configured. "
                "Set bitmagnet_url in [search] section."
            )
        return None

    def _build_graphql_query(self, query: str) -> dict:
        """Build GraphQL query body with escaped search query.

        Args:
            query: Search term

        Returns:
            Dictionary with query field for POST body
        """
        # Escape query string for JSON
        escaped_query = json.dumps(query)[1:-1]  # Remove outer quotes

        # Replace placeholder in template
        query_str = self.GRAPHQL_QUERY.replace("$QUERY", escaped_query)

        return {"query": query_str}

    def _fetch_results(self, url: str, query_body: dict) -> dict:
        """Fetch and parse JSON results from Bitmagnet GraphQL API.

        Args:
            url: GraphQL endpoint URL
            query_body: GraphQL query dictionary

        Returns:
            Parsed JSON data as dict

        Raises:
            Exception: If request fails or response invalid
        """
        try:
            # Convert query body to JSON
            post_data = json.dumps(query_body).encode("utf-8")

            logger.debug(f"Bitmagnet: requesting URL: {url}")
            with urlopen_post(url, data=post_data, timeout=30) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            # Check for GraphQL errors
            if "errors" in response_data:
                error_msgs = [
                    err.get("message", "Unknown error")
                    for err in response_data["errors"]
                ]
                raise Exception(f"GraphQL error: {'; '.join(error_msgs)}")

            return response_data

        except urllib.error.HTTPError as e:
            # Read error response body for more details
            error_body = ""
            try:
                if e.fp:
                    error_body = e.fp.read().decode("utf-8")
                    logger.error(
                        f"Bitmagnet HTTP {e.code} response: {error_body}"
                    )
            except Exception:
                pass

            if e.code in (401, 403):
                raise Exception("Bitmagnet access denied (check URL)")
            elif e.code == 404:
                raise Exception(
                    "Bitmagnet GraphQL endpoint not found (check URL)"
                )
            raise Exception(f"HTTP error {e.code}: {e.reason}")

        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot connect to Bitmagnet at {self.bitmagnet_url}: "
                f"{e.reason}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Bitmagnet response: {e}")

    def _fetch_content_details(self, info_hash: str) -> dict[str, Any] | None:
        """Fetch detailed content metadata for a torrent by info hash.

        Args:
            info_hash: Torrent info hash

        Returns:
            Dictionary of additional fields or None if fetch fails
        """
        if self._config_error:
            return None

        try:
            # Build GraphQL query for details
            escaped_hash = json.dumps(info_hash)[1:-1]
            query_str = self.GRAPHQL_DETAILS_QUERY.replace(
                "$INFOHASH", escaped_hash
            )
            query_body = {"query": query_str}

            # Fetch with 5-second timeout
            url = f"{self.bitmagnet_url.rstrip('/')}/graphql"
            post_data = json.dumps(query_body).encode("utf-8")

            logger.debug(f"Bitmagnet: fetching content details for {info_hash}")
            with urlopen_post(url, data=post_data, timeout=5) as response:
                response_data = json.loads(response.read().decode("utf-8"))

            # Navigate to content object
            items = (
                response_data.get("data", {})
                .get("torrentContent", {})
                .get("search", {})
                .get("items", [])
            )

            if not items or not items[0].get("content"):
                return None

            content = items[0]["content"]
            return self._parse_content_details(content)

        except Exception as e:
            logger.debug(f"Bitmagnet: error fetching content details: {e}")
            return None

    def _parse_content_details(self, content: dict[str, Any]) -> dict[str, Any]:
        """Parse content details into displayable fields.

        Args:
            content: Content object from GraphQL response

        Returns:
            Dictionary of formatted fields (mostly strings, but may include
            lists for complex fields like external_links)
        """
        fields: dict[str, Any] = {}

        # Extract various field types
        self._parse_simple_content_fields(content, fields)
        self._parse_numeric_content_fields(content, fields)
        self._parse_additional_content_fields(content, fields)

        return fields

    def _parse_simple_content_fields(
        self, content: dict[str, Any], fields: dict[str, Any]
    ) -> None:
        """Parse simple string fields from content."""
        simple_fields = [
            ("title", "content_title"),
            ("originalTitle", "original_title"),
            ("overview", "overview"),
        ]

        for source_key, target_key in simple_fields:
            value = content.get(source_key)
            if value:
                fields[target_key] = value

    def _parse_numeric_content_fields(
        self, content: dict[str, Any], fields: dict[str, Any]
    ) -> None:
        """Parse numeric fields from content."""
        if content.get("releaseYear"):
            fields["release_year"] = str(content["releaseYear"])

        if content.get("runtime"):
            fields["runtime"] = f"{content['runtime']} min"

        if content.get("voteAverage"):
            avg = content["voteAverage"]
            count = content.get("voteCount", 0)
            fields["rating"] = f"{avg:.1f}/10 ({count} votes)"

        if content.get("popularity"):
            fields["popularity"] = f"{content['popularity']:.1f}"

    def _parse_additional_content_fields(
        self, content: dict[str, Any], fields: dict[str, Any]
    ) -> None:
        """Parse additional fields from content."""
        # Boolean fields
        if content.get("adult"):
            fields["adult"] = "Yes"

        # Release date
        if content.get("releaseDate"):
            fields["release_date"] = content["releaseDate"]

        # Original language
        orig_lang = content.get("originalLanguage")
        if orig_lang and isinstance(orig_lang, dict):
            lang_name = orig_lang.get("name")
            if lang_name:
                fields["original_language"] = lang_name

        # External links - store as list of tuples for separate section
        ext_links = content.get("externalLinks", [])
        if ext_links:
            link_tuples = []
            for link in ext_links:
                if not isinstance(link, dict):
                    continue
                url = link.get("url")
                meta_source = link.get("metadataSource", {})
                source_name = meta_source.get("name", "Link")
                if url:
                    link_tuples.append((source_name, url))

            if link_tuples:
                # Store as list for _format_links_section to process
                fields["external_links"] = link_tuples

    def _process_results(self, data: dict) -> list[SearchResult]:
        """Process API response and convert to SearchResult list.

        Args:
            data: Parsed GraphQL JSON response

        Returns:
            List of SearchResult objects
        """
        if not data or "data" not in data:
            return []

        # Navigate GraphQL response structure
        items = (
            data.get("data", {})
            .get("torrentContent", {})
            .get("search", {})
            .get("items", [])
        )

        if not items:
            return []

        results = []
        for item in items:
            result = self._parse_torrent_item(item)
            if result:
                results.append(result)

        return results

    def _parse_torrent_item(self, item: dict[str, Any]) -> SearchResult | None:
        """Parse a single torrent item from Bitmagnet GraphQL response.

        Args:
            item: Single item dict from GraphQL response

        Returns:
            SearchResult or None if parsing fails
        """
        try:
            # Extract torrent object (required)
            torrent = item.get("torrent")
            if not torrent:
                return None

            # Extract required fields
            title = torrent.get("name")
            info_hash = torrent.get("infoHash")
            magnet_link = torrent.get("magnetUri")

            if not title:
                return None

            if not info_hash:
                return None

            if not magnet_link:
                return None

            # Extract optional numeric fields
            # Prefer item-level seeders/leechers over torrent-level
            seeders = item.get("seeders") or torrent.get("seeders")
            leechers = item.get("leechers") or torrent.get("leechers")
            size = torrent.get("size")
            files_count = torrent.get("filesCount")

            # Parse upload date
            upload_date = self._parse_publish_date(item)

            # Build extended metadata fields
            fields = self._build_fields(item)

            # Detect category from contentType
            categories = self._detect_category(item)

            page_url = (
                f"{self.bitmagnet_url.rstrip('/')}/webui/torrents/"
                f"permalink/{info_hash}"
            )

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                categories=categories,
                seeders=seeders,
                leechers=leechers,
                downloads=None,
                size=size,
                files_count=files_count,
                upload_date=upload_date,
                page_url=page_url,
                freeleech=True,  # Public
                fields=fields,
            )

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Bitmagnet: failed to parse item: {e}")
            return None

    def _parse_publish_date(self, item: dict[str, Any]) -> datetime | None:
        """Parse publish date from item.

        Args:
            item: Item dict from Bitmagnet GraphQL response

        Returns:
            datetime object or None if parsing fails
        """
        publish_date = item.get("publishedAt")
        if not publish_date:
            return None

        try:
            # Handle ISO 8601 format with Z timezone
            return datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _detect_category(self, item: dict[str, Any]) -> list[Category]:
        """Detect category from Bitmagnet contentType field.

        Maps Bitmagnet ContentType enum to StandardCategories using
        CONTENT_TYPE_CATEGORY_MAP. Unknown or missing types return
        empty list.

        Args:
            item: Item dict from Bitmagnet GraphQL response

        Returns:
            List containing detected category, or empty list if unknown
        """
        content_type = item.get("contentType")
        if not content_type:
            return []

        content_type_lower = content_type.lower()
        category = self.CONTENT_TYPE_CATEGORY_MAP.get(content_type_lower)

        return [category] if category else []

    def _build_fields(self, item: dict[str, Any]) -> dict[str, str] | None:
        """Build provider-specific fields dict from extended metadata.

        Args:
            item: Item dict from Bitmagnet GraphQL response

        Returns:
            Dictionary of provider-specific fields or None if empty
        """
        torrent = item.get("torrent", {})
        fields: dict[str, str] = {}

        # Extract all field types
        self._extract_content_fields(item, fields)
        self._extract_video_fields(item, fields)
        self._extract_timestamp_fields(item, torrent, fields)
        self._extract_list_fields(torrent, fields)
        self._extract_complex_fields(item, torrent, fields)

        return fields if fields else None

    def _extract_content_fields(
        self, item: dict[str, Any], fields: dict[str, str]
    ) -> None:
        """Extract content metadata fields."""
        field_map = [
            ("contentType", "content_type"),
            ("contentSource", "content_source"),
            ("contentId", "content_id"),
        ]
        self._extract_simple_fields(item, fields, field_map)

    def _extract_video_fields(
        self, item: dict[str, Any], fields: dict[str, str]
    ) -> None:
        """Extract video metadata fields."""
        field_map = [
            ("releaseGroup", "release_group"),
            ("videoResolution", "video_resolution"),
            ("videoSource", "video_source"),
            ("videoCodec", "video_codec"),
            ("video3d", "video_3d"),
            ("videoModifier", "video_modifier"),
        ]
        self._extract_simple_fields(item, fields, field_map)

    def _extract_timestamp_fields(
        self,
        item: dict[str, Any],
        torrent: dict[str, Any],
        fields: dict[str, str],
    ) -> None:
        """Extract and format timestamp fields from item and torrent."""
        item_field_map = [
            ("createdAt", "item_created_at"),
            ("updatedAt", "item_updated_at"),
        ]
        torrent_field_map = [
            ("createdAt", "torrent_created_at"),
            ("updatedAt", "torrent_updated_at"),
        ]

        # Extract and format item timestamps
        for source_key, target_key in item_field_map:
            value = item.get(source_key)
            if value:
                formatted = self._format_timestamp(value)
                if formatted:
                    fields[target_key] = formatted

        # Extract and format torrent timestamps
        for source_key, target_key in torrent_field_map:
            value = torrent.get(source_key)
            if value:
                formatted = self._format_timestamp(value)
                if formatted:
                    fields[target_key] = formatted

    def _extract_list_fields(
        self, torrent: dict[str, Any], fields: dict[str, str]
    ) -> None:
        """Extract list fields that need joining."""
        list_field_map = [
            ("fileTypes", "file_types"),
            ("tagNames", "tag_names"),
        ]
        for source_key, target_key in list_field_map:
            value = torrent.get(source_key, [])
            if value:
                fields[target_key] = ", ".join(value)

    def _extract_complex_fields(
        self,
        item: dict[str, Any],
        torrent: dict[str, Any],
        fields: dict[str, str],
    ) -> None:
        """Extract complex fields with custom formatting."""
        languages = self._format_languages(item.get("languages", []))
        if languages:
            fields["languages"] = languages

        episodes = self._format_episodes(item.get("episodes"))
        if episodes:
            fields["episodes"] = episodes

        sources = self._format_sources(torrent.get("sources", []))
        if sources:
            fields["sources"] = sources

    def _extract_simple_fields(
        self,
        source: dict[str, Any],
        fields: dict[str, str],
        field_map: list[tuple[str, str]],
    ) -> None:
        """Extract simple string fields from source to fields dict."""
        for source_key, target_key in field_map:
            value = source.get(source_key)
            if value:
                fields[target_key] = value

    def _format_languages(self, languages: list[dict]) -> str:
        """Format languages list to comma-separated string.

        Args:
            languages: List of language dicts with 'name' field

        Returns:
            Comma-separated language names or empty string
        """
        if not languages:
            return ""

        names = []
        for lang in languages:
            if isinstance(lang, dict) and "name" in lang:
                names.append(lang["name"])

        return ", ".join(names) if names else ""

    def _format_episodes(self, episodes: dict | None) -> str:
        """Format episodes dict to readable string.

        Args:
            episodes: Episodes dict with 'label' and 'seasons' fields

        Returns:
            Formatted episode string or empty string
        """
        if not episodes:
            return ""

        parts = []

        # Add label if present
        label = episodes.get("label")
        if label:
            parts.append(label)

        # Format seasons
        seasons = episodes.get("seasons", [])
        if seasons:
            season_parts = []
            for season in seasons:
                season_num = season.get("season")
                episode_list = season.get("episodes", [])

                if season_num is not None and episode_list:
                    # Format as S01E01-E05
                    if len(episode_list) == 1:
                        season_parts.append(
                            f"S{season_num:02d}E{episode_list[0]:02d}"
                        )
                    else:
                        first_ep = min(episode_list)
                        last_ep = max(episode_list)
                        season_parts.append(
                            f"S{season_num:02d}E{first_ep:02d}-E{last_ep:02d}"
                        )

            if season_parts:
                parts.append(f"({', '.join(season_parts)})")

        return " ".join(parts) if parts else ""

    def _format_sources(self, sources: list[dict]) -> str:
        """Format sources list to detailed string.

        Args:
            sources: List of source dicts with 'name', 'key', etc.

        Returns:
            Formatted source information or empty string
        """
        if not sources:
            return ""

        source_parts = []
        for source in sources:
            if not isinstance(source, dict):
                continue

            name = source.get("name", "")
            key = source.get("key", "")
            seeders = source.get("seeders")
            leechers = source.get("leechers")

            # Build source entry with available data
            parts = []
            if name:
                parts.append(name)
            elif key:
                parts.append(key)

            # Add peer counts if available
            peer_info = []
            if seeders is not None:
                peer_info.append(f"S:{seeders}")
            if leechers is not None:
                peer_info.append(f"L:{leechers}")

            if peer_info:
                parts.append(f"({'/'.join(peer_info)})")

            if parts:
                source_parts.append(" ".join(parts))

        return ", ".join(source_parts) if source_parts else ""

    def _format_timestamp(self, timestamp: str) -> str:
        """Format ISO 8601 timestamp to human-readable format.

        Args:
            timestamp: ISO 8601 timestamp string

        Returns:
            Formatted timestamp string or empty string if parsing fails
        """
        if not timestamp:
            return ""

        try:
            # Parse ISO 8601 format with Z timezone
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            # Format as: 2025-12-16 14:30
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            return timestamp  # Return original if parsing fails
