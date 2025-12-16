"""Bitmagnet torrent search provider implementation."""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ...util.log import get_logger, log_time
from ..base import BaseSearchProvider
from ..models import SearchResult
from ..util import urlopen_post

logger = get_logger()


class BitmagnetProvider(BaseSearchProvider):
    """Search provider for Bitmagnet (self-hosted torrent DHT search).

    Bitmagnet provides access to DHT-crawled torrents via GraphQL API.
    Documentation: https://bitmagnet.io
    """

    # GraphQL query template with $QUERY placeholder
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
        releaseGroup
        id
        infoHash
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
        videoCodec
        publishedAt
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
          }
        }
      }
    }
  }
}"""

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

        Prints extended metadata from the search result.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with Bitmagnet details
        """
        if not result.fields:
            return ""

        md = ""

        # Metadata section
        metadata_fields = [
            ("release_group", "Release Group"),
            ("video_resolution", "Video Resolution"),
            ("video_codec", "Video Codec"),
            ("languages", "Languages"),
            ("episodes", "Episodes"),
        ]

        metadata_lines = []
        for field_key, field_label in metadata_fields:
            value = result.fields.get(field_key)
            if value:
                metadata_lines.append(f"- **{field_label}:** {value}\n")

        if metadata_lines:
            md += "## Metadata\n"
            md += "".join(metadata_lines)

        # Sources section
        sources = result.fields.get("sources")
        if sources:
            md += "\n## Sources\n"
            md += f"- {sources}\n"

        # Tags section
        tags = result.fields.get("tag_names")
        if tags:
            md += "\n## Tags\n"
            md += f"- {tags}\n"

        # File info section
        file_info_fields = [
            ("file_types", "File Types"),
            ("created_at", "Created"),
            ("updated_at", "Updated"),
        ]

        file_info_lines = []
        for field_key, field_label in file_info_fields:
            value = result.fields.get(field_key)
            if value:
                file_info_lines.append(f"- **{field_label}:** {value}\n")

        if file_info_lines:
            md += "\n## File Info\n"
            md += "".join(file_info_lines)

        return md

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
            seeders = torrent.get("seeders")
            leechers = torrent.get("leechers")
            size = torrent.get("size")
            files_count = torrent.get("filesCount")

            # Parse upload date
            upload_date = self._parse_publish_date(item)

            # Build extended metadata fields
            fields = self._build_fields(item)

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                categories=[],  # TODO: detect category
                seeders=seeders,
                leechers=leechers,
                downloads=None,
                size=size,
                files_count=files_count,
                upload_date=upload_date,
                page_url=None,  # TODO: page url
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

    def _build_fields(self, item: dict[str, Any]) -> dict[str, str] | None:
        """Build provider-specific fields dict from extended metadata.

        Args:
            item: Item dict from Bitmagnet GraphQL response

        Returns:
            Dictionary of provider-specific fields or None if empty
        """
        torrent = item.get("torrent", {})
        fields = {}

        # Release group
        release_group = item.get("releaseGroup")
        if release_group:
            fields["release_group"] = release_group

        # Video resolution
        video_resolution = item.get("videoResolution")
        if video_resolution:
            fields["video_resolution"] = video_resolution

        # Video codec
        video_codec = item.get("videoCodec")
        if video_codec:
            fields["video_codec"] = video_codec

        # Languages
        languages = self._format_languages(item.get("languages", []))
        if languages:
            fields["languages"] = languages

        # Episodes
        episodes = self._format_episodes(item.get("episodes"))
        if episodes:
            fields["episodes"] = episodes

        # Sources
        sources = self._format_sources(torrent.get("sources", []))
        if sources:
            fields["sources"] = sources

        # File types
        file_types = torrent.get("fileTypes", [])
        if file_types:
            fields["file_types"] = ", ".join(file_types)

        # Tag names
        tag_names = torrent.get("tagNames", [])
        if tag_names:
            fields["tag_names"] = ", ".join(tag_names)

        # Created/Updated timestamps
        created_at = torrent.get("createdAt")
        if created_at:
            fields["created_at"] = created_at

        updated_at = torrent.get("updatedAt")
        if updated_at:
            fields["updated_at"] = updated_at

        return fields if fields else None

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
        """Format sources list to comma-separated string.

        Args:
            sources: List of source dicts with 'name' field

        Returns:
            Comma-separated source names or empty string
        """
        if not sources:
            return ""

        names = []
        for source in sources:
            if isinstance(source, dict) and "name" in source:
                names.append(source["name"])

        return ", ".join(names) if names else ""
