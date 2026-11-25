# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Prowlarr provider requests (without Prowlarr)."""

from unittest.mock import patch

import pytest

from src.tewi.search.providers.prowlarr import ProwlarrProvider

API_KEY = "0123456789abcdef"


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        response = mock.return_value.__enter__.return_value
        response.read.return_value = b"[]"
        yield mock


@pytest.fixture
def provider():
    return ProwlarrProvider("http://prowlarr:9696", API_KEY)


class TestApiKeyInHeader:
    """API key is sent in header, so it doesn't get to access logs."""

    def test_indexers_request(self, provider, mock_urlopen):
        provider._fetch_indexers(provider._build_indexers_url())

        url = mock_urlopen.call_args.args[0]
        headers = mock_urlopen.call_args.kwargs["headers"]
        assert API_KEY not in url
        assert headers == {"X-Api-Key": API_KEY}

    def test_search_request(self, provider, mock_urlopen):
        url = provider._build_search_url("ubuntu", None, ["1"])
        provider._fetch_results(url)

        url = mock_urlopen.call_args.args[0]
        headers = mock_urlopen.call_args.kwargs["headers"]
        assert API_KEY not in url
        assert "query=ubuntu" in url
        assert headers == {"X-Api-Key": API_KEY}


class TestParseResultInfoHash:
    HASH = "C12FE1C06BBA254A9DC9F519B335AA7C1367A88A"

    @staticmethod
    def parse(provider, **fields):
        return provider._parse_result(
            {
                "title": "Title",
                "downloadUrl": "http://prowlarr/dl",
                "indexerFlags": [],
                **fields,
            }
        )

    def test_hash_is_normalized(self, provider):
        result = self.parse(provider, infoHash=self.HASH)

        assert result.info_hash == self.HASH.lower()

    @pytest.mark.parametrize("info_hash", [None, "", "abc"])
    def test_result_without_valid_hash_is_kept(self, provider, info_hash):
        result = self.parse(provider, infoHash=info_hash)

        assert result.info_hash is None
        assert result.magnet_link is None
        assert result.torrent_link == "http://prowlarr/dl"

    def test_result_without_links_is_skipped(self, provider):
        assert self.parse(provider, downloadUrl=None) is None
