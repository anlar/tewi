# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for The Pirate Bay provider (without TPB)."""

import json
from unittest.mock import patch

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.tpb import TPBProvider

TORRENT = {
    "id": "59191690",
    "name": "Example Linux 22.04",
    "info_hash": "0123456789ABCDEF0123456789ABCDEF01234567",
    "leechers": "11",
    "seeders": "34",
    "size": "3654957056",
    "num_files": "1",
    "username": "uploader1",
    "added": "1652877231",
    "status": "vip",
    "category": "303",
    "imdb": "",
}


# API response when nothing is found
NO_RESULTS = [
    {
        "id": "0",
        "name": "No results returned",
        "info_hash": "0000000000000000000000000000000000000000",
        "leechers": "0",
        "seeders": "0",
        "num_files": "0",
        "size": "0",
        "username": "",
        "added": "0",
        "status": "member",
        "category": "0",
        "imdb": "",
        "total_found": "1",
    }
]


@pytest.fixture
def provider():
    return TPBProvider()


def mock_response(mock, data):
    response = mock.return_value.__enter__.return_value
    response.read.return_value = json.dumps(data).encode()


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        mock_response(mock, [TORRENT])
        yield mock


MOVIES = [201, 202, 204, 207, 209, 210, 211, 299]


class TestSearch:
    def test_search_request(self, provider, mock_urlopen):
        results = provider.search(" example ")

        url = mock_urlopen.call_args.args[0]
        assert url == "https://apibay.org/q.php?q=example&cat=0"
        assert len(results) == 1

    @pytest.mark.parametrize(
        "categories, expected",
        [
            (None, []),
            ([StandardCategories.MOVIES], MOVIES),
            ([StandardCategories.MOVIES_UHD], MOVIES),
            ([StandardCategories.TV], [205, 206, 208, 212]),
            (
                [StandardCategories.MOVIES, StandardCategories.TV],
                sorted(MOVIES + [205, 206, 208, 212]),
            ),
            (
                [StandardCategories.AUDIO],
                [101, 102, 103, 104, 199, 203],
            ),
            # PC and Mac games are in TPB games range
            (
                [StandardCategories.PC],
                [301, 302, 303, 304, 305, 306, 399, 401, 402],
            ),
            (
                [StandardCategories.CONSOLE],
                [403, 404, 405, 406, 407, 408, 499],
            ),
            ([StandardCategories.BOOKS], [601, 602, 603, 604, 605, 699]),
            # Other has only range code
            ([StandardCategories.OTHER], [600]),
        ],
    )
    def test_convert(self, provider, categories, expected):
        assert provider._convert_categories_to_tpb(categories) == expected

    def test_search_request_categories(self, provider, mock_urlopen):
        provider.search(
            "example", [StandardCategories.TV, StandardCategories.OTHER]
        )

        url = mock_urlopen.call_args.args[0]
        assert url.endswith("&cat=205%2C206%2C208%2C212%2C600")

    def test_no_results(self, provider, mock_urlopen):
        mock_response(mock_urlopen, NO_RESULTS)

        assert provider.search("example") == []

    def test_invalid_response(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b"not json"

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("example")

    def test_invalid_torrents_are_skipped(self, provider, mock_urlopen):
        mock_response(mock_urlopen, ["junk", None, 1, [], TORRENT])

        results = provider.search("example")

        assert [r.title for r in results] == [TORRENT["name"]]


class TestCategories:
    @pytest.mark.parametrize(
        "code, expected",
        [
            ("207", (StandardCategories.MOVIES_HD,)),
            ("601", (StandardCategories.BOOKS_EBOOK,)),
            # Unknown subcategory falls back to parent
            ("298", (StandardCategories.MOVIES,)),
            ("900", ()),
        ],
    )
    def test_result_category(self, provider, code, expected):
        result = provider._parse_torrent({**TORRENT, "category": code})

        assert result.categories == expected


class TestInvalidTorrent:
    def test_invalid_date_is_skipped(self, provider, caplog):
        torrent = {**TORRENT, "added": str(10**30)}

        assert provider._parse_torrent(torrent) is None
        assert "skipping invalid search result '59191690'" in caplog.text


class TestPageUrl:
    def test_page_url(self, provider):
        result = provider._parse_torrent(TORRENT)

        assert result.page_url == (
            "https://thepiratebay.org/description.php?id=59191690"
        )

    @pytest.mark.parametrize("torrent_id", ["1&x=y", "1#foo", "", None])
    def test_invalid_id_has_no_page_url(self, provider, torrent_id):
        result = provider._parse_torrent({**TORRENT, "id": torrent_id})

        assert result.page_url is None
