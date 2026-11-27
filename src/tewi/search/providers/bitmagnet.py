# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bitmagnet torrent search provider implementation."""

import json
import urllib.error
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
    MAX_DETAILS_FILES,
    MAX_ERROR_BODY_SIZE,
    details_value,
    format_files,
    local_time,
    parse_iso_date,
    read_response,
)

logger = get_logger()


class BitmagnetProvider(BaseSearchProvider):
    """Search provider for Bitmagnet (self-hosted torrent DHT search).

    Bitmagnet provides access to DHT-crawled torrents via GraphQL API.
    Documentation: https://bitmagnet.io
    Schema: https://github.com/bitmagnet-io/bitmagnet/tree/main/graphql
    """

    # Max number of results
    # Content metadata and files are downloaded from GraphQL API
    remote_details = True

    RESULTS_LIMIT = 100

    # GraphQL query for search, facets filter results by content type
    SEARCH_QUERY = """query Search(
  $query: String!
  $limit: Int!
  $facets: TorrentContentFacetsInput
) {
  torrentContent {
    search(
      input: {
        queryString: $query
        limit: $limit
        orderBy: [{ field: seeders, descending: true }]
        facets: $facets
      }
    ) {
      items {
        infoHash
        contentType
        contentSource
        contentId
        languages {
          name
        }
        episodes {
          label
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
          name
          size
          seeders
          leechers
          filesCount
          magnetUri
          fileTypes
          tagNames
          createdAt
          updatedAt
          sources {
            key
            name
            seeders
            leechers
          }
        }
      }
    }
  }
}"""

    # GraphQL query for torrent details: content metadata and files
    DETAILS_QUERY = """query Details($infoHash: Hash20!, $filesLimit: Int!) {
  torrentContent {
    search(input: { infoHashes: [$infoHash], limit: 1 }) {
      items {
        content {
          title
          releaseDate
          releaseYear
          adult
          originalLanguage {
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
              name
            }
            url
          }
        }
      }
    }
  }
  torrent {
    files(
      input: {
        infoHashes: [$infoHash]
        limit: $filesLimit
        orderBy: [{ field: path }]
      }
    ) {
      items {
        path
        size
      }
    }
  }
}"""

    # Mapping of Bitmagnet ContentType to StandardCategories (None is
    # unknown content type), based on Jackett's bitmagnet.yml
    CONTENT_TYPE_CATEGORY_MAP: dict[str | None, Category] = {
        "movie": StandardCategories.MOVIES,
        "tv_show": StandardCategories.TV,
        "music": StandardCategories.AUDIO,
        "ebook": StandardCategories.BOOKS_EBOOK,
        "comic": StandardCategories.BOOKS_COMICS,
        "audiobook": StandardCategories.AUDIO_AUDIOBOOK,
        "game": StandardCategories.PC_GAMES,
        "software": StandardCategories.PC,
        "xxx": StandardCategories.XXX,
        None: StandardCategories.OTHER,
    }

    # Search result fields shown in details: (item key, field key)
    ITEM_FIELDS = [
        ("contentType", "content_type"),
        ("contentSource", "content_source"),
        ("contentId", "content_id"),
        ("releaseGroup", "release_group"),
        ("videoResolution", "video_resolution"),
        ("videoSource", "video_source"),
        ("videoCodec", "video_codec"),
        ("video3d", "video_3d"),
        ("videoModifier", "video_modifier"),
    ]

    # Details sections fields: (field key, label)
    CONTENT_FIELDS = [
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
        ("file_types", "File Types"),
        ("tag_names", "Tags"),
        ("sources", "Sources"),
    ]
    VIDEO_FIELDS = [
        ("video_resolution", "Resolution"),
        ("video_source", "Source"),
        ("video_codec", "Codec"),
        ("video_3d", "3D"),
        ("video_modifier", "Modifier"),
    ]
    RELEASE_FIELDS = [
        ("release_group", "Release Group"),
        ("languages", "Languages"),
        ("episodes", "Episodes"),
    ]
    TIMESTAMP_FIELDS = [
        ("item_created_at", "Item Created"),
        ("item_updated_at", "Item Updated"),
        ("torrent_created_at", "Torrent Created"),
        ("torrent_updated_at", "Torrent Updated"),
    ]

    def __init__(
        self, bitmagnet_url: str | None = None, timeout: int | None = None
    ) -> None:
        """Initialize Bitmagnet provider with configuration.

        Args:
            bitmagnet_url: Base URL of Bitmagnet instance
            timeout: Default timeout in seconds for search requests
        """
        super().__init__(timeout)
        self.bitmagnet_url: str | None = bitmagnet_url
        self._config_error: str | None = self._validate_config(bitmagnet_url)

    @property
    def id(self) -> str:
        return "bitmagnet"

    @property
    def name(self) -> str:
        return "Bitmagnet"

    @property
    def short_name(self) -> str:
        return "BitMT"

    @log_time
    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search Bitmagnet for torrents via GraphQL API.

        Args:
            query: Search term
            categories: Categories to filter by (optional)
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

        content_types = self._content_types(categories)
        if content_types == []:
            return []

        variables: dict[str, Any] = {
            "query": query.strip(),
            "limit": self.RESULTS_LIMIT,
            "facets": None,
        }
        if content_types:
            variables["facets"] = {"contentType": {"filter": content_types}}

        data = self._graphql(self.SEARCH_QUERY, variables)
        items = self._dig(data, "torrentContent", "search", "items")
        if not isinstance(items, list):
            raise Exception("Failed to parse Bitmagnet response: no items")

        return [r for i in items if (r := self._parse_torrent_item(i))]

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        """Generate Bitmagnet-specific details for right column.

        Shows metadata from the search result and fetches content
        metadata and files from GraphQL API.

        Args:
            result: Search result to format

        Returns:
            Sections with Bitmagnet details
        """
        return self._details_sections(
            result, self._fetch_details(result.info_hash)
        )

    def details_extended_offline(
        self, result: SearchResult
    ) -> list[DetailsSection] | None:
        if not result.info_hash:
            return self._details_sections(result, None)
        details = self._details_cache.get(result.info_hash)
        if details is None:
            return None
        return self._details_sections(result, details)

    def _details_sections(
        self, result: SearchResult, details: dict[str, Any] | None
    ) -> list[DetailsSection]:
        """Build details sections from result and downloaded details.

        Args:
            result: Search result to format
            details: Downloaded details, None if they could not be loaded

        Returns:
            Sections with provider details
        """
        if not result.extra:
            return []

        fields = dict(result.extra)
        files: list[DetailsSection] = []
        if details:
            fields.update(self._parse_content_details(details.get("content")))
            # Files query total count is limited by requested number of files
            files = format_files(
                self._dig(details.get("files"), "items"),
                ("path",),
                "size",
                result.files_count,
            )

        overview = None
        # Long text is shown as paragraph, not squeezed into field value
        if fields.get("overview"):
            overview = DetailsSection("Overview", text=str(fields["overview"]))

        sections = [
            self._format_section("Content", fields, self.CONTENT_FIELDS),
            overview,
            self._format_section("Video", fields, self.VIDEO_FIELDS),
            self._format_section("Release", fields, self.RELEASE_FIELDS),
            self._format_links(fields.get("external_links")),
            *files,
            self._format_section("Timestamps", fields, self.TIMESTAMP_FIELDS),
        ]
        return [s for s in sections if s]

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

    def _content_types(
        self, categories: list[Category] | None
    ) -> list[str | None] | None:
        """Convert categories to Bitmagnet content types to search.

        Args:
            categories: Selected categories

        Returns:
            Content types (None is unknown type), None to search all, or
            empty list if Bitmagnet has none of selected categories
        """
        if not categories:
            return None

        parents = {c.parent or c for c in categories}
        return [
            content_type
            for content_type, category in self.CONTENT_TYPE_CATEGORY_MAP.items()
            if (category.parent or category) in parents
        ]

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict:
        """Send GraphQL request to Bitmagnet.

        Args:
            query: GraphQL query
            variables: Query variables

        Returns:
            Response data

        Raises:
            Exception: If request fails, response is invalid or has errors
        """
        url = f"{self.bitmagnet_url.rstrip('/')}/graphql"
        body = json.dumps({"query": query, "variables": variables})

        try:
            logger.debug(f"Bitmagnet: requesting URL: {url}")
            with self.urlopen_post(url, data=body.encode()) as response:
                data = json.loads(read_response(response).decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read error response body for more details
            try:
                if e.fp:
                    error_body = e.fp.read(MAX_ERROR_BODY_SIZE).decode(
                        "utf-8", errors="replace"
                    )
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

        if not isinstance(data, dict):
            raise Exception("Failed to parse Bitmagnet response: not object")

        errors = data.get("errors")
        if errors:
            messages = [
                str(e.get("message") or "unknown error")
                if isinstance(e, dict)
                else str(e)
                for e in errors
            ]
            raise Exception(f"GraphQL error: {'; '.join(messages)}")

        result = data.get("data")
        return result if isinstance(result, dict) else {}

    @log_time
    def _fetch_details(self, info_hash: str | None) -> dict[str, Any] | None:
        """Fetch content metadata and files of torrent.

        Args:
            info_hash: Torrent info hash

        Returns:
            Dictionary with "content" and "files", or None if they could
            not be loaded
        """
        if not info_hash:
            return None
        return self._cached_details(
            info_hash, lambda: self._download_details(info_hash)
        )

    @log_time
    def _download_details(self, info_hash: str) -> dict[str, Any] | None:
        """Download content metadata and files, see `_fetch_details`."""
        try:
            data = self._graphql(
                self.DETAILS_QUERY,
                {"infoHash": info_hash, "filesLimit": MAX_DETAILS_FILES},
            )
        except Exception as e:
            logger.warning(f"Bitmagnet: failed to fetch details: {e}")
            return None

        items = self._dig(data, "torrentContent", "search", "items")
        item = items[0] if isinstance(items, list) and items else None
        return {
            "content": self._dig(item, "content"),
            "files": self._dig(data, "torrent", "files"),
        }

    def _parse_torrent_item(self, item: Any) -> SearchResult | None:
        """Parse a single torrent item from Bitmagnet GraphQL response.

        Args:
            item: Single item from GraphQL response

        Returns:
            SearchResult or None if item is invalid
        """
        if not isinstance(item, dict):
            return None

        try:
            torrent = item.get("torrent")
            if not isinstance(torrent, dict):
                return None

            title = torrent.get("name")
            info_hash = parse_info_hash(item.get("infoHash"))
            magnet_link = torrent.get("magnetUri")
            if not title or not info_hash or not magnet_link:
                return None

            category = self.CONTENT_TYPE_CATEGORY_MAP.get(
                item.get("contentType")
            )

            return SearchResult(
                title=title,
                info_hash=info_hash,
                magnet_link=magnet_link,
                torrent_link=None,
                provider=self.name,
                provider_id=self.id,
                provider_short=self.short_name,
                categories=(category,) if category else (),
                seeders=self._peers(item, torrent, "seeders"),
                leechers=self._peers(item, torrent, "leechers"),
                downloads=None,
                size=parse_count(torrent.get("size")),
                files_count=parse_count(torrent.get("filesCount")),
                upload_date=local_time(parse_iso_date(item.get("publishedAt"))),
                page_url=(
                    f"{self.bitmagnet_url.rstrip('/')}/webui/torrents/"
                    f"permalink/{info_hash}"
                ),
                freeleech=True,  # Public
                extra=self._build_fields(item, torrent),
            )

        except Exception:
            logger.exception(
                "Bitmagnet: skipping invalid search result "
                f"{item.get('infoHash')!r}"
            )
            return None

    def _build_fields(
        self, item: dict[str, Any], torrent: dict[str, Any]
    ) -> dict[str, str]:
        """Build provider-specific fields shown in details.

        Args:
            item: Item from GraphQL response
            torrent: Torrent of item

        Returns:
            Dictionary of non-empty fields, as strings
        """
        fields = {
            key: str(item[source])
            for source, key in self.ITEM_FIELDS
            if item.get(source)
        }

        for source, key in (
            ("fileTypes", "file_types"),
            ("tagNames", "tag_names"),
        ):
            values = torrent.get(source)
            if isinstance(values, list) and values:
                fields[key] = ", ".join(str(v) for v in values)

        languages = [
            str(lang["name"])
            for lang in item.get("languages") or []
            if isinstance(lang, dict) and lang.get("name")
        ]
        if languages:
            fields["languages"] = ", ".join(languages)

        # Label lists seasons and episodes, e.g. "S01E01-E05, S03"
        episodes = self._dig(item, "episodes", "label")
        if episodes:
            fields["episodes"] = str(episodes)

        sources = self._format_sources(torrent.get("sources"))
        if sources:
            fields["sources"] = sources

        for source, value, key in (
            (item, "createdAt", "item_created_at"),
            (item, "updatedAt", "item_updated_at"),
            (torrent, "createdAt", "torrent_created_at"),
            (torrent, "updatedAt", "torrent_updated_at"),
        ):
            date = parse_iso_date(source.get(value))
            if date:
                fields[key] = local_time(date).strftime("%Y-%m-%d %H:%M")

        return fields

    def _format_sources(self, sources: Any) -> str:
        """Format torrent sources with their peer counts.

        Args:
            sources: Sources from GraphQL response

        Returns:
            Sources, e.g. "DHT (S:5/L:1)", or empty string
        """
        if not isinstance(sources, list):
            return ""

        parts = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            name = source.get("name") or source.get("key")
            if not name:
                continue
            peers = [
                f"{label}:{source[key]}"
                for key, label in (("seeders", "S"), ("leechers", "L"))
                if source.get(key) is not None
            ]
            parts.append(f"{name} ({'/'.join(peers)})" if peers else name)
        return ", ".join(str(p) for p in parts)

    def _parse_content_details(self, content: Any) -> dict[str, Any]:
        """Parse content metadata into displayable fields.

        Args:
            content: Content object from GraphQL response

        Returns:
            Dictionary of fields, as strings, except external_links,
            which is list of (name, url)
        """
        if not isinstance(content, dict):
            return {}

        fields: dict[str, Any] = {}
        for source, key in (
            ("title", "content_title"),
            ("originalTitle", "original_title"),
            ("overview", "overview"),
            ("releaseYear", "release_year"),
            ("releaseDate", "release_date"),
        ):
            if content.get(source):
                fields[key] = str(content[source])

        if content.get("runtime"):
            fields["runtime"] = f"{content['runtime']} min"

        vote_average = content.get("voteAverage")
        if isinstance(vote_average, int | float) and vote_average:
            votes = parse_count(content.get("voteCount")) or 0
            fields["rating"] = f"{vote_average:.1f}/10 ({votes} votes)"

        popularity = content.get("popularity")
        if isinstance(popularity, int | float) and popularity:
            fields["popularity"] = f"{popularity:.1f}"

        if content.get("adult"):
            fields["adult"] = "Yes"

        language = self._dig(content, "originalLanguage", "name")
        if language:
            fields["original_language"] = str(language)

        links = [
            (str(self._dig(link, "metadataSource", "name") or "Link"), url)
            for link in content.get("externalLinks") or []
            if isinstance(link, dict) and (url := link.get("url"))
        ]
        if links:
            fields["external_links"] = links

        return fields

    def _format_section(
        self, title: str, fields: dict[str, Any], defs: list[tuple[str, str]]
    ) -> DetailsSection | None:
        """Format section with fields present in details.

        Args:
            title: Section title
            fields: Field values
            defs: List of (field key, label)

        Returns:
            Section, or None if it has no fields
        """
        rows: list[tuple[str, str | DetailsLink]] = [
            (label, str(fields[key])) for key, label in defs if fields.get(key)
        ]
        return DetailsSection(title, fields=tuple(rows)) if rows else None

    def _format_links(self, links: Any) -> DetailsSection | None:
        """Format external links section."""
        if not links or not isinstance(links, list):
            return None
        return DetailsSection(
            "Links",
            fields=tuple((name, details_value(url)) for name, url in links),
        )

    def _peers(
        self, item: dict[str, Any], torrent: dict[str, Any], key: str
    ) -> int | None:
        """Get peers count of item, or of torrent if item has none."""
        count = parse_count(item.get(key))
        return count if count is not None else parse_count(torrent.get(key))

    def _dig(self, data: Any, *keys: str) -> Any:
        """Get nested value from dictionaries, or None if it's missing."""
        for key in keys:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
        return data
