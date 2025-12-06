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
from src.tewi.service.search.jackett_provider import JackettProvider
from src.tewi.common import SearchResultDTO, JackettCategories


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
        # info_hash can now be None - removed assertion
        assert result.magnet_link is not None, \
            "Magnet link should not be None"

    def validate_info_hash(self, info_hash: str | None):
        """Validate info hash format (40 hex characters) if present.

        Args:
            info_hash: Info hash string or None
        """
        if info_hash is None:
            return  # Allow None
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
            if provider.name == "Torrents-CSV":
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

        # Page URL should be None or valid URL
        if result.page_url is not None:
            assert result.page_url.startswith(('http://', 'https://')), \
                f"Page URL should start with http:// or https://, " \
                f"got {result.page_url}"

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

    def validate_categories(self, categories: list, valid_categories: set):
        """Validate categories list contains valid categories.

        Args:
            categories: List of Category objects
            valid_categories: Set of valid Category objects
        """
        # Empty categories list is allowed (for providers without category support)
        if not categories:
            return

        for category in categories:
            assert category in valid_categories, \
                f"Category '{category.full_name}' not in valid set"

    @pytest.mark.xfail(reason="External provider API may be unavailable or unreliable")
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

            # Validate categories
            self.validate_categories(result.categories, valid_categories)


class TestYTSProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for YTS provider."""

    def get_provider(self):
        return YTSProvider()

    def get_search_query(self) -> str:
        return "matrix"

    def get_valid_categories(self) -> set:
        return {JackettCategories.MOVIES}

    def requires_trackers(self) -> bool:
        return True


class TestTPBProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for The Pirate Bay provider."""

    def get_provider(self):
        return TPBProvider()

    def get_search_query(self) -> str:
        return "ubuntu"

    def get_valid_categories(self) -> set:
        return {JackettCategories.AUDIO, JackettCategories.MOVIES,
                JackettCategories.PC, JackettCategories.CONSOLE,
                JackettCategories.XXX, JackettCategories.OTHER,
                JackettCategories.BOOKS}

    def requires_trackers(self) -> bool:
        return False


class TestTorrentsCsvProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for Torrents-CSV provider."""

    def get_provider(self):
        return TorrentsCsvProvider()

    def get_search_query(self) -> str:
        return "debian"

    def get_valid_categories(self) -> set:
        # TorrentsCSV returns empty categories, but refinement may detect
        # categories from torrent names
        return {JackettCategories.AUDIO, JackettCategories.MOVIES,
                JackettCategories.PC, JackettCategories.CONSOLE,
                JackettCategories.XXX, JackettCategories.BOOKS,
                JackettCategories.OTHER}

    def requires_trackers(self) -> bool:
        return False


class TestNyaaProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for Nyaa.si provider."""

    def get_provider(self):
        return NyaaProvider()

    def get_search_query(self) -> str:
        return "anime"

    def get_valid_categories(self) -> set:
        # Nyaa categories are now mapped to Jackett categories based on categoryId
        return {
            # Anime categories
            JackettCategories.TV_ANIME,
            # Audio categories
            JackettCategories.AUDIO,
            JackettCategories.AUDIO_LOSSLESS,
            # Literature categories
            JackettCategories.BOOKS,
            # Live Action categories
            JackettCategories.TV,
            # Pictures categories
            JackettCategories.OTHER,
            # Software categories
            JackettCategories.PC,
            JackettCategories.PC_ISO,
            JackettCategories.PC_GAMES,
        }

    def requires_trackers(self) -> bool:
        return True


class TestJackettProviderIntegration(BaseProviderIntegrationTest):
    """Integration tests for Jackett provider.

    Note: Requires local Jackett instance running at configured URL
    with valid API key. Uses environment variables for configuration.
    """

    def get_provider(self):
        import os
        jackett_url = os.environ.get(
            'TEST_JACKETT_URL',
            'http://localhost:9117'
        )
        api_key = os.environ.get(
            'TEST_JACKETT_API_KEY',
            '66uf0ahso78pjke00t09bzlf93ufq3we'
        )
        return JackettProvider(jackett_url, api_key)

    def get_search_query(self) -> str:
        return "ubuntu"

    def get_valid_categories(self) -> set:
        # Jackett can return any category
        return set(JackettCategories.all_categories())

    def requires_trackers(self) -> bool:
        # Jackett may or may not have trackers depending on indexer
        return False

    def test_missing_config(self):
        """Test behavior when configuration is missing."""
        # Test with no URL
        provider = JackettProvider(None, "test_key")
        with pytest.raises(Exception) as exc_info:
            provider.search("test")
        assert "URL not configured" in str(exc_info.value)

        # Test with no API key
        provider = JackettProvider("http://localhost:9117", None)
        with pytest.raises(Exception) as exc_info:
            provider.search("test")
        assert "API key not configured" in str(exc_info.value)
