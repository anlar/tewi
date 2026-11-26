# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Torrents-CSV provider (without Torrents-CSV)."""

import json
import urllib.error
from datetime import datetime
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.torrentscsv import TorrentsCsvProvider

TORRENT = {
    "id": 1,
    "infohash": "0123456789ABCDEF0123456789ABCDEF01234567",
    "name": "Example Linux 22.04 Installer",
    "size_bytes": 3654957056,
    "created_unix": 1652877231,
    "seeders": 34,
    "leechers": 11,
    "completed": 120,
    "scraped_date": 1700000000,
}


@pytest.fixture
def provider():
    return TorrentsCsvProvider()


def mock_response(mock, data):
    response = mock.return_value.__enter__.return_value
    response.read.return_value = json.dumps(data).encode()


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        mock_response(mock, {"torrents": [TORRENT], "next": None})
        yield mock


class TestSearch:
    def test_search_request(self, provider, mock_urlopen):
        results = provider.search(" example ")

        url = mock_urlopen.call_args.args[0]
        assert url == "https://torrents-csv.com/service/search?q=example"
        assert len(results) == 1

    @pytest.mark.parametrize("query", ["", "  ", "ab", " ab ", "é"])
    def test_short_query(self, provider, mock_urlopen, query):
        assert provider.search(query) == []
        mock_urlopen.assert_not_called()

    @pytest.mark.parametrize("query", ["abc", "日本"])
    def test_min_query(self, provider, mock_urlopen, query):
        assert len(provider.search(query)) == 1

    @pytest.mark.parametrize("data", [{"torrents": []}, {"torrents": None}, {}])
    def test_no_results(self, provider, mock_urlopen, data):
        mock_response(mock_urlopen, data)

        assert provider.search("example") == []

    def test_invalid_json(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b"not json"

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("example")

    @pytest.mark.parametrize(
        "data", [[TORRENT], None, "junk", {"torrents": {"a": TORRENT}}]
    )
    def test_invalid_response(self, provider, mock_urlopen, data):
        mock_response(mock_urlopen, data)

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("example")

    def test_invalid_torrents_are_skipped(self, provider, mock_urlopen):
        torrents = [
            "junk",
            None,
            1,
            [],
            {**TORRENT, "name": 123},
            {**TORRENT, "name": " "},
            {**TORRENT, "infohash": "not a hash"},
            TORRENT,
        ]
        mock_response(mock_urlopen, {"torrents": torrents})

        results = provider.search("example")

        assert [r.title for r in results] == [TORRENT["name"]]


def page(ids, next_id):
    """Build API page with torrents of given IDs."""
    torrents = [
        {**TORRENT, "id": i, "infohash": f"{i:040x}", "name": f"Torrent {i}"}
        for i in ids
    ]
    return {"torrents": torrents, "next": next_id}


def mock_pages(mock, *pages):
    """Mock API to return given pages (or raise exceptions) in order."""
    responses = []
    for p in pages:
        if isinstance(p, Exception):
            responses.append(p)
            continue
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            p
        ).encode()
        responses.append(response)
    mock.side_effect = responses


def requested_after(mock):
    """Return "after" parameter of each request (None if not sent)."""
    result = []
    for call in mock.call_args_list:
        query = parse_qs(urlsplit(call.args[0]).query)
        result.append(int(query["after"][0]) if "after" in query else None)
    return result


class TestPagination:
    def test_pages_are_loaded_after_last_id(self, provider, mock_urlopen):
        mock_pages(
            mock_urlopen,
            page([1, 2], 2),
            page([3, 4], 4),
            page([5], 5),
            page([], None),
        )

        results = provider.search("example")

        assert [r.title for r in results] == [
            f"Torrent {i}" for i in range(1, 6)
        ]
        assert requested_after(mock_urlopen) == [None, 2, 4, 5]

    def test_max_pages(self, provider, mock_urlopen):
        mock_pages(mock_urlopen, *(page([i], i) for i in range(1, 10)))

        results = provider.search("example")

        assert len(results) == provider.MAX_PAGES
        assert mock_urlopen.call_count == provider.MAX_PAGES

    @pytest.mark.parametrize("next_id", [None, "junk", -1, True])
    def test_no_next_page(self, provider, mock_urlopen, next_id):
        mock_pages(mock_urlopen, page([1], next_id), page([2], None))

        assert len(provider.search("example")) == 1
        assert mock_urlopen.call_count == 1

    def test_empty_page_stops(self, provider, mock_urlopen):
        mock_pages(mock_urlopen, page([], 7), page([2], None))

        assert provider.search("example") == []
        assert mock_urlopen.call_count == 1

    @pytest.mark.parametrize("next_id", [3, 2])
    def test_cursor_not_moving_forward_stops(
        self, provider, mock_urlopen, next_id
    ):
        mock_pages(
            mock_urlopen, page([1, 3], 3), page([2], next_id), page([4], None)
        )

        assert len(provider.search("example")) == 3
        assert mock_urlopen.call_count == 2

    def test_next_page_as_text(self, provider, mock_urlopen):
        mock_pages(mock_urlopen, page([1], "1"), page([2], None))

        assert len(provider.search("example")) == 2
        assert requested_after(mock_urlopen) == [None, 1]

    @pytest.mark.parametrize(
        "error",
        [urllib.error.URLError("timed out"), json.JSONDecodeError("x", "", 0)],
    )
    def test_failed_next_page_keeps_results(
        self, provider, mock_urlopen, caplog, error
    ):
        mock_pages(mock_urlopen, page([1], 1), error)

        results = provider.search("example")

        assert [r.title for r in results] == ["Torrent 1"]
        assert "failed to load page 2" in caplog.text

    def test_failed_next_page_after_invalid_torrents(
        self, provider, mock_urlopen
    ):
        mock_pages(
            mock_urlopen,
            {"torrents": ["junk"], "next": 1},
            urllib.error.URLError("timed out"),
        )

        assert provider.search("example") == []

    def test_failed_first_page_raises(self, provider, mock_urlopen):
        mock_pages(mock_urlopen, urllib.error.URLError("timed out"))

        with pytest.raises(Exception, match="Network error"):
            provider.search("example")


class TestParseTorrent:
    def test_result(self, provider):
        result = provider._parse_torrent(TORRENT)

        assert result.info_hash == TORRENT["infohash"].lower()
        assert result.categories == (StandardCategories.PC,)
        assert result.seeders == 34
        assert result.leechers == 11
        assert result.downloads == 120
        assert result.size == 3654957056
        assert (
            result.upload_date
            == datetime.fromtimestamp(1652877231).astimezone()
        )
        assert (
            result.extra["scraped_date"]
            == datetime.fromtimestamp(1700000000).astimezone()
        )

    @pytest.mark.parametrize(
        "value", [10**20, -(10**15), "junk", True, 0, None, 1.5]
    )
    def test_invalid_dates_are_skipped(self, provider, value):
        torrent = {**TORRENT, "created_unix": value, "scraped_date": value}

        result = provider._parse_torrent(torrent)

        assert result.title == TORRENT["name"]
        assert result.upload_date is None
        assert "scraped_date" not in result.extra

    def test_date_as_text(self, provider):
        torrent = {**TORRENT, "created_unix": "1652877231"}

        result = provider._parse_torrent(torrent)

        assert (
            result.upload_date
            == datetime.fromtimestamp(1652877231).astimezone()
        )


class TestDetails:
    def test_scraped_date(self, provider):
        result = provider._parse_torrent(TORRENT)

        sections = provider.details_extended(result)

        expected = datetime.fromtimestamp(1700000000).strftime("%Y-%m-%d %H:%M")
        assert sections[0].fields == (("Last Scraped", expected),)

    def test_no_scraped_date(self, provider):
        result = provider._parse_torrent({**TORRENT, "scraped_date": None})

        assert provider.details_extended(result) == []
