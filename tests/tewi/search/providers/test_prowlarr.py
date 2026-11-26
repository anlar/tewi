# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Prowlarr provider (without Prowlarr)."""

import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

from src.tewi.search.models import DetailsLink, StandardCategories
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

    def test_hash_with_torrent_link_does_not_build_magnet(self, provider):
        # Magnet built from hash has no trackers (private torrents need them)
        result = self.parse(provider, infoHash=self.HASH)

        assert result.magnet_link is None
        assert result.torrent_link == "http://prowlarr/dl"

    def test_hash_without_links_builds_magnet(self, provider):
        result = self.parse(provider, infoHash=self.HASH, downloadUrl=None)

        assert result.magnet_link.startswith(
            f"magnet:?xt=urn:btih:{self.HASH.lower()}"
        )


MAGNET = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a"

RESULT = {
    "id": 0,
    "guid": MAGNET,
    "title": "Example 1080p",
    "sortTitle": "example 1080p",
    "indexer": "The Pirate Bay",
    "indexerId": 1,
    "protocol": "torrent",
    "infoHash": "C12FE1C06BBA254A9DC9F519B335AA7C1367A88A",
    "magnetUrl": "http://prowlarr/1/download?apikey=key&link=x",
    "downloadUrl": "http://prowlarr/1/download?apikey=key&link=y",
    "infoUrl": "https://tpb.example/description.php?id=1",
    "commentUrl": "https://tpb.example/description.php?id=1",
    "posterUrl": "https://img.example/poster.jpg",
    "indexerFlags": ["freeleech", "internal"],
    "imdbId": 111161,
    "tmdbId": 0,
    "tvdbId": 0,
    "tvMazeId": 0,
    "seeders": 10,
    "leechers": 4,
    "size": 1024,
}


def set_response(mock, data) -> None:
    mock.return_value.__enter__.return_value.read.return_value = json.dumps(
        data
    ).encode()


class TestSearch:
    def test_request(self, mock_urlopen):
        provider = ProwlarrProvider("http://prowlarr:9696", API_KEY, True)

        provider.search(
            "example",
            [StandardCategories.MOVIES, StandardCategories.TV],
            ["1", "2"],
        )

        url = mock_urlopen.call_args.args[0]
        assert parse_qs(urlsplit(url).query) == {
            "query": ["example"],
            "indexerIds": ["1", "2"],
            "categories": ["2000", "5000"],
        }

    @pytest.mark.parametrize(
        "multi, indexers", [(False, ["1"]), (True, ["all"]), (True, None)]
    )
    def test_all_indexers(self, mock_urlopen, multi, indexers):
        provider = ProwlarrProvider("http://prowlarr:9696", API_KEY, multi)

        provider.search("example", indexers=indexers)

        assert "indexerIds" not in mock_urlopen.call_args.args[0]

    def test_result(self, provider, mock_urlopen):
        set_response(mock_urlopen, [RESULT])

        [result] = provider.search("example")

        assert result.magnet_link == MAGNET
        assert result.torrent_link == RESULT["downloadUrl"]
        assert result.provider == "The Pirate Bay"
        assert (result.seeders, result.leechers) == (10, 4)
        assert result.freeleech
        assert result.page_url == RESULT["infoUrl"]

    @pytest.mark.parametrize(
        "fields, magnet, torrent",
        [
            # Proxy magnet link is used without magnet in guid
            (
                {"guid": "https://tpb.example/1"},
                RESULT["magnetUrl"],
                RESULT["downloadUrl"],
            ),
            # Prowlarr download link is preferred, as it works for private
            # trackers too
            (
                {"guid": "https://t.example/1.torrent", "magnetUrl": None},
                None,
                RESULT["downloadUrl"],
            ),
            (
                {
                    "guid": "https://t.example/1.torrent",
                    "magnetUrl": None,
                    "downloadUrl": None,
                },
                None,
                "https://t.example/1.torrent",
            ),
            ({"guid": 123}, RESULT["magnetUrl"], RESULT["downloadUrl"]),
        ],
    )
    def test_links(self, provider, mock_urlopen, fields, magnet, torrent):
        set_response(mock_urlopen, [{**RESULT, **fields}])

        [result] = provider.search("example")

        assert (result.magnet_link, result.torrent_link) == (magnet, torrent)

    def test_usenet_result_is_skipped(self, provider, mock_urlopen):
        set_response(mock_urlopen, [{**RESULT, "protocol": "usenet"}])

        assert provider.search("example") == []

    def test_missing_flags_and_indexer(self, provider, mock_urlopen):
        set_response(
            mock_urlopen, [{**RESULT, "indexerFlags": None, "indexer": None}]
        )

        [result] = provider.search("example")

        assert not result.freeleech
        assert result.provider == "Unknown"

    def test_invalid_result_does_not_fail_search(self, provider, mock_urlopen):
        set_response(mock_urlopen, ["x", {**RESULT, "title": ["x"]}, RESULT])

        assert [r.title for r in provider.search("example")] == [
            "Example 1080p"
        ]

    def test_invalid_response(self, provider, mock_urlopen):
        set_response(mock_urlopen, {"message": "x"})

        with pytest.raises(Exception, match="not a list"):
            provider.search("example")

    def test_error_message(self, provider, mock_urlopen):
        body = b'{"message": "All selected indexers are unavailable"}'
        mock_urlopen.side_effect = HTTPError(
            "url", 400, "Bad Request", {}, BytesIO(body)
        )

        with pytest.raises(
            Exception, match="HTTP error 400: All selected indexers"
        ):
            provider.search("example")

    def test_details(self, provider, mock_urlopen):
        set_response(mock_urlopen, [RESULT])
        [result] = provider.search("example")

        [section] = provider.details_extended(result)

        assert section.fields == (
            ("IMDB", DetailsLink("https://www.imdb.com/title/tt0111161/")),
            ("Indexer Flags", "freeleech, internal"),
            ("Poster", DetailsLink("https://img.example/poster.jpg")),
        )

    def test_details_without_fields(self, provider, mock_urlopen):
        set_response(
            mock_urlopen,
            [{**RESULT, "imdbId": 0, "posterUrl": None, "indexerFlags": []}],
        )
        [result] = provider.search("example")

        assert provider.details_extended(result) == []


class TestIndexers:
    def test_only_enabled_torrent_indexers(self, provider, mock_urlopen):
        provider.multi_indexer = True
        set_response(
            mock_urlopen,
            [
                {"id": 1, "name": "TPB", "enable": True, "protocol": "torrent"},
                {"id": 2, "name": "Off", "enable": False},
                {"id": 3, "name": "NZB", "enable": True, "protocol": "usenet"},
                {
                    "id": 4,
                    "name": "RSS",
                    "enable": True,
                    "supportsSearch": False,
                },
                {"id": 5, "enable": True},
                "x",
            ],
        )

        indexers = provider.indexers()

        assert [(i.id, i.name) for i in indexers] == [("prowlarr:1", "TPB")]

    def test_invalid_response(self, provider, mock_urlopen, caplog):
        provider.multi_indexer = True
        set_response(mock_urlopen, {"message": "x"})

        assert provider.indexers() == []
        assert "Failed to load Prowlarr indexers" in caplog.text
