"""Abstract base class for torrent search providers."""

import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from ...common import SearchResultDTO, Category, JackettCategories, IndexerDTO
from ...util.print import print_size


class BaseSearchProvider(ABC):
    """Abstract base class for torrent search providers.

    Each provider implements search functionality for a specific
    public tracker or torrent search engine.
    """

    # User-Agent string to imitate a popular browser
    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36")

    @abstractmethod
    def _search_impl(self, query: str,
                     categories: list[Category] | None = None) -> list[
            SearchResultDTO]:
        """Provider-specific search implementation.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)

        Returns:
            List of SearchResultDTO objects

        Raises:
            Exception: If search fails
        """
        pass

    def search(self, query: str,
               categories: list[Category] | None = None) -> list[
            SearchResultDTO]:
        """Search for torrents and refine unknown categories.

        This method calls the provider-specific implementation and
        automatically refines UNKNOWN categories by analyzing torrent names.

        Args:
            query: Search term
            categories: Category objects to filter by (optional)

        Returns:
            List of SearchResultDTO objects with refined categories

        Raises:
            Exception: If search fails
        """
        results = self._search_impl(query, categories)
        return self._refine_results(results)

    def _urlopen(self, url: str, timeout: int = 30):
        """Open URL with User-Agent header.

        Creates a Request object with User-Agent header set to imitate
        a popular browser, preventing blocking by search providers.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds (default: 10)

        Returns:
            HTTP response context manager

        Raises:
            urllib.error.URLError: If network request fails
        """
        request = urllib.request.Request(url)
        request.add_header('User-Agent', self.USER_AGENT)
        return urllib.request.urlopen(request, timeout=timeout)

    @abstractmethod
    def id(self) -> str:
        """Return unique provider identifier for internal use.

        Returns:
            Unique string identifier (e.g., 'yts', 'jackett', 'tpb')
        """
        pass

    def indexers(self) -> list[IndexerDTO]:
        """Return list of available indexers for this provider.

        For most providers, this returns a single indexer (the provider
        itself) which is basic implementation. For meta-providers like
        Jackett, this returns all configured indexers.

        Returns:
            List of (indexer_id, indexer_name) tuples
        """
        return [IndexerDTO(self.id(), f"{self.name}")]

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    def _build_magnet_link(self, info_hash: str, name: str,
                           trackers: list[str] = None) -> str:
        """Build a magnet link from info hash, name, and optional trackers.

        Args:
            info_hash: 40-character hex string torrent info hash
            name: Torrent name to encode in magnet link
            trackers: Optional list of tracker URLs to append

        Returns:
            Complete magnet link string
        """
        encoded_name = urllib.parse.quote(name)
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}"

        if trackers:
            for tracker in trackers:
                encoded_tracker = urllib.parse.quote(tracker, safe='/:')
                magnet += f"&tr={encoded_tracker}"

        return magnet

    def _detect_category_from_name(self, name: str) -> Category | None:
        """Detect category from torrent name using pattern matching.

        Args:
            name: Torrent name/title

        Returns:
            Detected Jackett Category or None if no pattern matches
        """
        name_lower = name.lower()

        # AUDIO: Check for audio file extensions and keywords
        audio_patterns = [
            '.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma', '.alac',
            'album', 'discography', 'soundtrack', 'ost', 'music',
        ]
        if any(pattern in name_lower for pattern in audio_patterns):
            return JackettCategories.AUDIO

        # VIDEO: Check for video file extensions and keywords
        video_patterns = [
            '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
            'movie', 'film', '1080p', '720p', '2160p', '4k', 'bluray',
            'webrip', 'hdtv', 'x264', 'x265', 'hevc', 'dvdrip',
        ]
        if any(pattern in name_lower for pattern in video_patterns):
            return JackettCategories.MOVIES

        # OTHER: Check for documents, archives, and other content FIRST
        # (before SOFTWARE to avoid "ebook" matching "app" in application)
        other_patterns = [
            '.pdf', '.epub', '.mobi', '.azw', '.doc', '.txt',
            '.zip', '.rar', '.7z', '.tar',
            ' book', 'ebook', 'magazine', 'comic', 'tutorial',
        ]
        if any(pattern in name_lower for pattern in other_patterns):
            return JackettCategories.BOOKS

        # SOFTWARE: Check for software extensions and keywords
        software_patterns = [
            '.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.app',
            'software', 'program', 'application', 'installer', 'setup',
            'patch', 'crack', 'keygen', 'portable',
        ]
        if any(pattern in name_lower for pattern in software_patterns):
            return JackettCategories.PC

        # GAMES: Check for game-related keywords
        games_patterns = [
            'game', 'repack', 'fitgirl', 'codex', 'skidrow', 'plaza',
            'gog', 'steam', 'gameplay', 'pc game', 'ps4', 'ps5',
            'xbox', 'switch', 'nintendo',
        ]
        if any(pattern in name_lower for pattern in games_patterns):
            return JackettCategories.CONSOLE

        # XXX: Check for adult content keywords
        xxx_patterns = ['xxx', 'adult', '18+', 'nsfw', 'porn']
        if any(pattern in name_lower for pattern in xxx_patterns):
            return JackettCategories.XXX

        # No pattern matched
        return None

    def _refine_results(
            self,
            results: list[SearchResultDTO]) -> list[SearchResultDTO]:
        """Refine empty categories by detecting from torrent names.

        Creates new DTOs with refined categories where detection succeeds,
        preserving immutability of SearchResultDTO.

        Args:
            results: List of search results

        Returns:
            List with refined categories (new DTOs where category changed)
        """
        refined_results = []
        for result in results:
            # Only refine if categories list is empty
            if not result.categories:
                detected = self._detect_category_from_name(result.title)
                if detected:
                    # Create new DTO with detected category
                    result = SearchResultDTO(
                        title=result.title,
                        categories=[detected],
                        seeders=result.seeders,
                        leechers=result.leechers,
                        size=result.size,
                        files_count=result.files_count,
                        magnet_link=result.magnet_link,
                        info_hash=result.info_hash,
                        upload_date=result.upload_date,
                        provider=result.provider,
                        provider_id=result.provider_id,
                        page_url=result.page_url,
                        torrent_link=result.torrent_link,
                        fields=result.fields
                    )
            refined_results.append(result)
        return refined_results

    def details_common(self, result: SearchResultDTO) -> str:
        """Generate common torrent details for left column.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with common details
        """
        md = "## General\n"
        md += f"- **Provider:** {self.name}\n"

        # Display categories with full names
        if result.categories:
            category_names = ', '.join(cat.full_name for cat in result.categories)
            md += f"- **Category:** {category_names}\n"
        else:
            md += "- **Category:** Unknown\n"

        md += f"- **Info Hash:** `{result.info_hash}`\n"

        if result.page_url:
            md += f"- **Link:** {result.page_url}\n"

        md += "## Statistics\n"
        md += f"- **Size:** {print_size(result.size)}\n"
        md += f"- **Seeders:** {result.seeders}\n"
        md += f"- **Leechers:** {result.leechers}\n"

        if result.files_count is not None:
            md += f"- **Files:** {result.files_count}\n"

        if result.upload_date:
            date_str = result.upload_date.strftime('%Y-%m-%d %H:%M')
            md += f"- **Uploaded:** {date_str}\n"

        return md

    def details_extended(self, result: SearchResultDTO) -> str:
        """Generate provider-specific details for right column.

        Base implementation returns empty string.
        Subclasses should override to add provider-specific fields.

        Args:
            result: Search result to format

        Returns:
            Markdown-formatted string with provider-specific details
        """
        return ""
