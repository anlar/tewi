# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Jackett provider (without Jackett)."""

import json
import logging
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from src.tewi.search.models import StandardCategories
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
    assert indexers[0].source == "Jackett"

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


def test_discovery_reports_torznab_error_description(monkeypatch, caplog):
    provider = JackettProvider("http://localhost:9117", "key", True)
    response = b'<error code="100" description="Invalid API Key" />'
    monkeypatch.setattr(
        provider, "urlopen", Mock(return_value=BytesIO(response))
    )

    assert provider.indexers() == []
    assert "Failed to load Jackett indexers: Invalid API Key" in caplog.text
    assert provider._cached_indexers is None


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


class TestParseResultInfoHash:
    HASH = "C12FE1C06BBA254A9DC9F519B335AA7C1367A88A"

    @staticmethod
    def parse(**fields):
        provider = JackettProvider("http://jackett", "key")
        return provider._parse_result(
            {"Title": "Title", "Link": "http://jackett/dl/1", **fields}
        )

    def test_hash_is_normalized(self):
        result = self.parse(InfoHash=self.HASH)

        assert result.info_hash == self.HASH.lower()

    @pytest.mark.parametrize("info_hash", [None, "", "abc"])
    def test_result_without_valid_hash_is_kept(self, info_hash):
        result = self.parse(InfoHash=info_hash)

        assert result.info_hash is None
        assert result.magnet_link is None
        assert result.torrent_link == "http://jackett/dl/1"

    def test_result_without_links_is_skipped(self):
        assert self.parse(Link=None) is None


def search_response(results=(), indexers=()) -> BytesIO:
    return BytesIO(
        json.dumps(
            {"Results": list(results), "Indexers": list(indexers)}
        ).encode()
    )


RESULT = {
    "Title": "Example 1080p",
    "InfoHash": "C12FE1C06BBA254A9DC9F519B335AA7C1367A88A",
    "Link": "http://jackett/dl/1?jackett_apikey=key",
    "Tracker": "Example Tracker",
    "Seeders": 10,
    "Peers": 4,
    "Genres": ["Drama", "Comedy"],
    "CategoryDesc": "TV/HD",
    "Description": "Uploader: x<br>Example &amp; more",
    "DownloadVolumeFactor": 0.0,
    "UploadVolumeFactor": 1.0,
    "Gain": 105.2,
    "TrackerType": "public",
    "Poster": "http://jackett/img/1?jackett_apikey=key",
    "BlackholeLink": "http://jackett/bh/1?jackett_apikey=key",
}


class TestSearch:
    @pytest.fixture
    def urlopen(self, monkeypatch):
        mock = Mock(return_value=search_response([RESULT]))
        return mock

    def search(self, monkeypatch, urlopen, multi=False, **kwargs):
        provider = JackettProvider("http://localhost:9117", "key", multi)
        monkeypatch.setattr(provider, "urlopen", urlopen)
        return provider.search("example", **kwargs)

    def params(self, urlopen) -> dict[str, list[str]]:
        url = urlsplit(urlopen.call_args.args[0])
        assert url.path == "/api/v2.0/indexers/all/results"
        return parse_qs(url.query)

    def test_request(self, monkeypatch, urlopen):
        self.search(monkeypatch, urlopen)

        assert self.params(urlopen) == {"apikey": ["key"], "Query": ["example"]}

    def test_categories_are_repeated(self, monkeypatch, urlopen):
        self.search(
            monkeypatch,
            urlopen,
            categories=[StandardCategories.MOVIES, StandardCategories.TV],
        )

        assert self.params(urlopen)["Category"] == ["2000", "5000"]

    def test_selected_indexers(self, monkeypatch, urlopen):
        self.search(monkeypatch, urlopen, True, indexers=["alpha", "zeta"])

        urlopen.assert_called_once()
        assert self.params(urlopen)["Tracker[]"] == ["alpha,zeta"]

    @pytest.mark.parametrize(
        "multi, indexers", [(False, ["alpha"]), (True, ["all"]), (True, None)]
    )
    def test_all_indexers(self, monkeypatch, urlopen, multi, indexers):
        self.search(monkeypatch, urlopen, multi, indexers=indexers)

        assert "Tracker[]" not in self.params(urlopen)

    def test_api_key_is_not_logged(self, monkeypatch, urlopen, caplog):
        caplog.set_level(logging.DEBUG)

        self.search(monkeypatch, urlopen)

        assert "apikey=***" in caplog.text
        assert "apikey=key" not in caplog.text

    def test_result(self, monkeypatch, urlopen):
        [result] = self.search(monkeypatch, urlopen)

        # Search results API reports leechers as peers
        assert (result.seeders, result.leechers) == (10, 4)
        assert result.provider == "Example Tracker"
        assert result.extra["Genres"] == "Drama, Comedy"
        assert result.freeleech
        # Proxy links with API key are not shown
        assert "Poster" not in result.extra
        assert "BlackholeLink" not in result.extra

    def test_details(self, monkeypatch, urlopen):
        provider = JackettProvider("http://localhost:9117", "key")
        monkeypatch.setattr(provider, "urlopen", urlopen)
        [result] = provider.search("example")

        sections = provider.details_extended(result)

        assert [s.title for s in sections] == ["Indexer Info", "Description"]
        # Duplicates of main fields and internal values are hidden
        assert sections[0].fields == (
            ("Genres", "Drama, Comedy"),
            ("TrackerType", "public"),
        )
        assert sections[1].text == "Uploader: x\nExample & more"

    def test_invalid_result_does_not_fail_search(self, monkeypatch, urlopen):
        urlopen.return_value = search_response(
            ["x", {**RESULT, "Title": ["x"]}, RESULT]
        )

        results = self.search(monkeypatch, urlopen)

        assert [r.title for r in results] == ["Example 1080p"]

    def test_missing_tracker_name(self, monkeypatch, urlopen):
        urlopen.return_value = search_response(
            [{**RESULT, "Tracker": None, "TrackerId": "example"}]
        )

        [result] = self.search(monkeypatch, urlopen)

        assert result.provider == "example"

    @pytest.mark.parametrize("data", [[], {}, {"Results": "x"}])
    def test_invalid_response(self, monkeypatch, urlopen, data):
        urlopen.return_value = BytesIO(json.dumps(data).encode())

        with pytest.raises(Exception, match="Failed to parse Jackett"):
            self.search(monkeypatch, urlopen)

    def test_all_indexers_failed(self, monkeypatch, urlopen):
        error = "Jackett.Common.IndexerException: Connection refused\n  at X"
        urlopen.return_value = search_response(
            indexers=[
                {"ID": "alpha", "Name": "Alpha", "Status": 1, "Error": error},
                {"ID": "zeta", "Name": "Zeta", "Status": 0, "Error": None},
            ]
        )

        with pytest.raises(Exception) as e:
            self.search(monkeypatch, urlopen)

        assert str(e.value) == (
            "All indexers failed (Alpha: Jackett.Common.IndexerException: "
            "Connection refused; Zeta: unknown error)"
        )

    def test_some_indexers_failed(self, monkeypatch, urlopen, caplog):
        urlopen.return_value = search_response(
            [RESULT],
            [
                {"Name": "Alpha", "Status": 2, "Results": 1},
                {"Name": "Zeta", "Status": 1, "Error": "Timeout"},
            ],
        )

        assert len(self.search(monkeypatch, urlopen)) == 1
        assert "Jackett indexer failed: Zeta: Timeout" in caplog.text

    def test_no_results(self, monkeypatch, urlopen):
        urlopen.return_value = search_response(
            indexers=[{"Name": "Alpha", "Status": 2, "Results": 0}]
        )

        assert self.search(monkeypatch, urlopen) == []
