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
