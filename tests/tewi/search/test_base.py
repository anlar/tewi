# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for BaseSearchProvider shared HTTP helpers."""

from typing import Any
from unittest.mock import patch

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.models import Category, DetailsSection, SearchResult
from tests.tewi.search.helpers import details_fields


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

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        return []


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

    @patch("src.tewi.search.base._urlopen")
    def test_passes_headers(self, mock_urlopen):
        """Test that extra headers are passed to urlopen."""
        provider = _StubProvider(timeout=45)

        provider.urlopen("http://example.com", headers={"X-Api-Key": "k"})

        mock_urlopen.assert_called_once_with(
            "http://example.com", timeout=45, headers={"X-Api-Key": "k"}
        )


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

    @patch("src.tewi.search.base._urlopen_post")
    def test_passes_headers(self, mock_urlopen_post):
        """Test that extra headers are passed to urlopen_post."""
        provider = _StubProvider()

        provider.urlopen_post(
            "http://example.com", data=b"{}", headers={"X-Api-Key": "k"}
        )

        mock_urlopen_post.assert_called_once_with(
            "http://example.com", data=b"{}", headers={"X-Api-Key": "k"}
        )


class TestDetailsCommon:
    @staticmethod
    def result(size: int | None, **kwargs: Any) -> SearchResult:
        return SearchResult(
            title="title",
            info_hash="a" * 40,
            magnet_link=None,
            torrent_link=None,
            provider="Stub",
            provider_id="stub",
            provider_short="S",
            size=size,
            **kwargs,
        )

    def test_size(self):
        sections = _StubProvider().details_common(self.result(1000))

        assert details_fields(sections)["Size"] == "1 kB"

    def test_unknown_size(self):
        sections = _StubProvider().details_common(self.result(None))

        assert details_fields(sections)["Size"] == "-"

    def test_zero_counts_are_shown(self):
        result = self.result(None, seeders=0, leechers=0, downloads=0)
        fields = details_fields(_StubProvider().details_common(result))

        assert fields["Seeders"] == "0"
        assert fields["Leechers"] == "0"
        assert fields["Downloads"] == "0"

    def test_unknown_values_are_dash(self):
        result = SearchResult(
            title="title",
            info_hash=None,
            magnet_link=None,
            torrent_link=None,
            provider="Stub",
            provider_id="stub",
            provider_short="S",
        )
        fields = details_fields(_StubProvider().details_common(result))

        assert fields == {
            "Provider": "Stub",
            "Category": "-",
            "Info Hash": "-",
            "Size": "-",
            "Seeders": "-",
            "Leechers": "-",
            "Downloads": "-",
            "Files": "-",
            "Uploaded": "-",
            "Freeleech": "No",
        }
