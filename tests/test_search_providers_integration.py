"""Integration tests for torrent search providers.

These tests make actual API calls to external services and may be slower
or fail if the services are unavailable.

Run with: pytest tests/test_search_providers_integration.py -v -m integration
"""

import pytest
from abc import ABC, abstractmethod
from datetime import datetime

from src.tewi.service.search.yts_provider import YTSProvider
from src.tewi.service.search.tpb_provider import TPBProvider
from src.tewi.service.search.torrentscsv_provider import TorrentsCsvProvider
from src.tewi.service.search.nyaa_provider import NyaaProvider
from src.tewi.common import SearchResultDTO, TorrentCategory


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class BaseProviderIntegrationTest(ABC):
    """Base class for provider integration tests.

    Each provider test class should inherit from this and implement
    the abstract methods to specify provider-specific configuration.
    """

    @abstractmethod
    def get_provider(self):
        """Return the provider instance to test.

        Returns:
            BaseSearchProvider: Provider instance
        """
        pass

    @abstractmethod
    def get_search_query(self) -> str:
        """Return the search query string for this provider.

        Returns:
            str: Search query
        """
        pass

    @abstractmethod
    def get_valid_categories(self) -> set:
        """Return set of valid categories for this provider.

        Returns:
            set: Valid category values (can include None)
        """
        pass

    @abstractmethod
    def requires_trackers(self) -> bool:
        """Return whether magnet links should have trackers.

        Returns:
            bool: True if magnet links should have &tr= parameters
        """
        pass

    def validate_result_list(self, results):
        """Validate that result list is not None and not empty.

        Args:
            results: List of search results
        """
        assert results is not None, "Results should not be None"
        assert isinstance(results, list), "Results should be a list"
        assert len(results) > 0, "Results should not be empty"

    def validate_result_structure(self, result):
        """Validate that result has all required fields.

        Args:
            result: SearchResultDTO instance
        """
        assert isinstance(result, SearchResultDTO), \
            f"Result should be SearchResultDTO, got {type(result)}"
        assert result.title is not None, "Title should not be None"
        assert len(result.title) > 0, "Title should not be empty"
        assert result.info_hash is not None, "Info hash should not be None"
        assert result.magnet_link is not None, \
            "Magnet link should not be None"

    def validate_info_hash(self, info_hash: str):
        """Validate info hash format (40 hex characters).

        Args:
            info_hash: Info hash string
        """
        assert len(info_hash) == 40, \
            f"Info hash should be 40 chars, got {len(info_hash)}"
        assert all(c in '0123456789abcdefABCDEF' for c in info_hash), \
            "Info hash should only contain hex characters"

    def validate_magnet_link(self, magnet_link: str, info_hash: str):
        """Validate magnet link format and content.

        Args:
            magnet_link: Magnet URI string
            info_hash: Expected info hash
        """
        assert magnet_link.startswith('magnet:?'), \
            "Magnet link should start with 'magnet:?'"
        assert 'xt=urn:btih:' in magnet_link, \
            "Magnet link should contain 'xt=urn:btih:'"
        assert info_hash.lower() in magnet_link.lower(), \
            "Magnet link should contain the info hash"

        # Check tracker requirements
        if self.requires_trackers():
            assert '&tr=' in magnet_link, \
                "Magnet link should contain trackers (&tr=)"
        else:
            # For TorrentsCSV, explicitly check NO trackers
            provider = self.get_provider()
            if provider.name == "torrentscsv":
                assert '&tr=' not in magnet_link, \
                    "TorrentsCSV magnet links should not have trackers"

    def validate_metadata(self, result: SearchResultDTO):
        """Validate metadata fields have reasonable values.

        Args:
            result: SearchResultDTO instance
        """
        # Size should be positive and reasonable
        assert result.size >= 0, "Size should be non-negative"
        assert result.size < 100 * 1024 ** 3, \
            f"Size should be less than 100GB, got {result.size}"

        # Seeders and leechers should be non-negative
        assert result.seeders >= 0, \
            f"Seeders should be non-negative, got {result.seeders}"
        assert result.leechers >= 0, \
            f"Leechers should be non-negative, got {result.leechers}"

    def validate_upload_date(self, upload_date):
        """Validate upload date if present.

        Args:
            upload_date: datetime object or None
        """
        if upload_date is not None:
            assert isinstance(upload_date, datetime), \
                f"Upload date should be datetime, got {type(upload_date)}"

            # Handle both timezone-aware and naive datetimes
            now = datetime.now(upload_date.tzinfo) \
                if upload_date.tzinfo else datetime.now()

            assert upload_date < now, \
                "Upload date should be in the past"

    def validate_category(self, category, valid_categories: set):
        """Validate category is in the valid set.

        Args:
            category: Category value
            valid_categories: Set of valid category values
        """
        assert category in valid_categories, \
            f"Category '{category}' not in valid set {valid_categories}"

    def test_provider_search(self):
        """Test provider search with single API call and validate all results.

        This test:
        1. Makes one search call to the provider
        2. Validates the result list is not None/empty
        3. Validates each result item has correct structure and data
        """
        provider = self.get_provider()
        query = self.get_search_query()
        valid_categories = self.get_valid_categories()

        # Make single search call
        results = provider.search(query)

        # Validate result list
        self.validate_result_list(results)

        # Validate each result (limit to first 5 for performance)
        for result in results[:5]:
            # Validate structure
            self.validate_result_structure(result)

            # Validate info hash
            self.validate_info_hash(result.info_hash)

            # Validate magnet link
            self.validate_magnet_link(result.magnet_link, result.info_hash)

            # Validate metadata
            self.validate_metadata(result)

            # Validate upload date if present
            self.validate_upload_date(result.upload_date)

            # Validate category
            self.validate_category(result.category, valid_categories)


class TestYTSProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for YTS provider."""

    def get_provider(self):
        return YTSProvider()

    def get_search_query(self) -> str:
        return "matrix"

    def get_valid_categories(self) -> set:
        return {TorrentCategory.VIDEO}

    def requires_trackers(self) -> bool:
        return True


class TestTPBProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for The Pirate Bay provider."""

    def get_provider(self):
        return TPBProvider()

    def get_search_query(self) -> str:
        return "ubuntu"

    def get_valid_categories(self) -> set:
        return {TorrentCategory.AUDIO, TorrentCategory.VIDEO,
                TorrentCategory.SOFTWARE, TorrentCategory.GAMES,
                TorrentCategory.XXX, TorrentCategory.OTHER,
                TorrentCategory.UNKNOWN}

    def requires_trackers(self) -> bool:
        return False


class TestTorrentsCsvProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for Torrents-CSV provider."""

    def get_provider(self):
        return TorrentsCsvProvider()

    def get_search_query(self) -> str:
        return "debian"

    def get_valid_categories(self) -> set:
        # TorrentsCSV returns UNKNOWN, but category refinement may detect
        # other categories from torrent names
        return {TorrentCategory.UNKNOWN, TorrentCategory.AUDIO,
                TorrentCategory.VIDEO, TorrentCategory.SOFTWARE,
                TorrentCategory.GAMES, TorrentCategory.XXX,
                TorrentCategory.OTHER}

    def requires_trackers(self) -> bool:
        return False


class TestNyaaProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for Nyaa.si provider."""

    def get_provider(self):
        return NyaaProvider()

    def get_search_query(self) -> str:
        return "anime"

    def get_valid_categories(self) -> set:
        # Nyaa categories are now mapped to basic categories
        return {TorrentCategory.AUDIO, TorrentCategory.VIDEO,
                TorrentCategory.SOFTWARE, TorrentCategory.GAMES,
                TorrentCategory.OTHER, TorrentCategory.UNKNOWN}

    def requires_trackers(self) -> bool:
        return True
