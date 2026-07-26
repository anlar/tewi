"""Unit tests for BaseSearchProvider shared HTTP helpers."""

from unittest.mock import patch

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.models import Category, SearchResult


class _StubProvider(BaseSearchProvider):
    """Minimal concrete provider for exercising base class behavior."""

    @property
    def id(self) -> str:
        return "stub"

    @property
    def name(self) -> str:
        return "Stub"

    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        return []

    def details_extended(self, result: SearchResult) -> str:
        return ""


class TestBaseSearchProviderTimeout:
    """Test cases for provider-level timeout configuration."""

    def test_default_timeout_is_none(self):
        """Test that a provider defaults to no configured timeout."""
        provider = _StubProvider()
        assert provider.timeout is None

    def test_custom_timeout(self):
        """Test that a provider stores the given timeout."""
        provider = _StubProvider(timeout=45)
        assert provider.timeout == 45


class TestBaseSearchProviderUrlopen:
    """Test cases for BaseSearchProvider.urlopen."""

    @patch("src.tewi.search.base._urlopen")
    def test_uses_provider_timeout_by_default(self, mock_urlopen):
        """Test that urlopen uses the provider's configured timeout."""
        provider = _StubProvider(timeout=45)

        provider.urlopen("http://example.com")

        mock_urlopen.assert_called_once_with("http://example.com", timeout=45)

    @patch("src.tewi.search.base._urlopen")
    def test_explicit_timeout_overrides_provider_timeout(self, mock_urlopen):
        """Test that an explicit timeout overrides the provider default."""
        provider = _StubProvider(timeout=45)

        provider.urlopen("http://example.com", timeout=10)

        mock_urlopen.assert_called_once_with("http://example.com", timeout=10)

    @patch("src.tewi.search.base._urlopen")
    def test_no_timeout_falls_back_to_urlopen_default(self, mock_urlopen):
        """Test that a provider without a timeout omits the argument."""
        provider = _StubProvider()

        provider.urlopen("http://example.com")

        mock_urlopen.assert_called_once_with("http://example.com")


class TestBaseSearchProviderUrlopenPost:
    """Test cases for BaseSearchProvider.urlopen_post."""

    @patch("src.tewi.search.base._urlopen_post")
    def test_uses_provider_timeout_by_default(self, mock_urlopen_post):
        """Test that urlopen_post uses the provider's configured timeout."""
        provider = _StubProvider(timeout=45)

        provider.urlopen_post("http://example.com", data=b"{}")

        mock_urlopen_post.assert_called_once_with(
            "http://example.com", data=b"{}", timeout=45
        )

    @patch("src.tewi.search.base._urlopen_post")
    def test_explicit_timeout_overrides_provider_timeout(
        self, mock_urlopen_post
    ):
        """Test that an explicit timeout overrides the provider default."""
        provider = _StubProvider(timeout=45)

        provider.urlopen_post("http://example.com", data=b"{}", timeout=5)

        mock_urlopen_post.assert_called_once_with(
            "http://example.com", data=b"{}", timeout=5
        )

    @patch("src.tewi.search.base._urlopen_post")
    def test_no_timeout_falls_back_to_urlopen_post_default(
        self, mock_urlopen_post
    ):
        """Test that a provider without a timeout omits the argument."""
        provider = _StubProvider()

        provider.urlopen_post("http://example.com", data=b"{}")

        mock_urlopen_post.assert_called_once_with(
            "http://example.com", data=b"{}"
        )
