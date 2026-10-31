"""Regression tests for Jackett discovery without tracker searches."""

from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from src.tewi.search.providers.jackett import JackettProvider

INDEXERS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<indexers>
    <indexer id="zeta" configured="true"><title>Zeta</title></indexer>
    <indexer id="alpha" configured="true">
        <title>Alpha &amp; Omega</title>
        <caps><searching><search available="yes" /></searching></caps>
    </indexer>
    <indexer id="unused" configured="false"><title>Unused</title></indexer>
    <indexer configured="true"><title>Missing ID</title></indexer>
    <indexer id="untitled" configured="true" />
</indexers>
"""


def test_discovery_uses_metadata_command_not_search(monkeypatch):
    provider = JackettProvider(
        "http://localhost:9117/jackett/", "key +&?", multi_indexer=True
    )
    urlopen = Mock(return_value=BytesIO(INDEXERS_XML))
    monkeypatch.setattr(provider, "urlopen", urlopen)

    indexers = provider.indexers()

    url = urlsplit(urlopen.call_args.args[0])
    assert url.path == "/jackett/api/v2.0/indexers/all/results/torznab/api"
    assert parse_qs(url.query) == {
        "apikey": ["key +&?"],
        "t": ["indexers"],
        "configured": ["true"],
    }
    assert [(indexer.id, indexer.name) for indexer in indexers] == [
        ("jackett:alpha", "Alpha & Omega"),
        ("jackett:zeta", "Zeta"),
    ]
    assert indexers[0].display_name == "Alpha & Omega [dim](Jackett)[/]"

    # Reopening the search dialog reuses metadata, not another HTTP request.
    assert provider.indexers() == indexers
    urlopen.assert_called_once()


def test_empty_configured_list_is_cached(monkeypatch):
    provider = JackettProvider("http://localhost:9117", "key", True)
    urlopen = Mock(return_value=BytesIO(b"<indexers />"))
    monkeypatch.setattr(provider, "urlopen", urlopen)

    assert provider.indexers() == []
    assert provider.indexers() == []
    urlopen.assert_called_once()


@pytest.mark.parametrize(
    "response", [b"not XML", b"<rss />", b'<error code="100" />']
)
def test_invalid_metadata_is_not_cached(monkeypatch, caplog, response):
    provider = JackettProvider("http://localhost:9117", "key", True)
    urlopen = Mock(side_effect=[BytesIO(response), BytesIO(INDEXERS_XML)])
    monkeypatch.setattr(provider, "urlopen", urlopen)

    assert provider.indexers() == []
    assert "Failed to load Jackett indexers" in caplog.text
    assert len(provider.indexers()) == 2
    assert urlopen.call_count == 2


@pytest.mark.parametrize("status", [401, 403])
def test_discovery_reports_invalid_api_key(monkeypatch, caplog, status):
    provider = JackettProvider("http://localhost:9117", "key", True)
    monkeypatch.setattr(
        provider,
        "urlopen",
        Mock(side_effect=HTTPError("http://localhost", status, "", {}, None)),
    )

    assert provider.indexers() == []
    assert "Invalid Jackett API key" in caplog.text
    assert provider._cached_indexers is None


def test_grouped_mode_does_not_request_metadata(monkeypatch):
    provider = JackettProvider("http://localhost:9117", "key")
    urlopen = Mock(side_effect=AssertionError("Unexpected HTTP request"))
    monkeypatch.setattr(provider, "urlopen", urlopen)

    assert [indexer.id for indexer in provider.indexers()] == ["jackett:all"]
    urlopen.assert_not_called()
