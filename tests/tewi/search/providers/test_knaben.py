# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Knaben provider (without Knaben)."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.knaben import KnabenProvider
from tests.tewi.search.helpers import details_fields, details_section

HIT = {
    "bytes": 5922042,
    "cachedOrigin": "The Pirate Bay",
    "category": "Books / EBooks",
    "categoryId": [9001000, 9000000],
    "date": "2023-12-29T17:45:36+00:00",
    "description": "Uploader: uploader1<br>Ren&eacute; [x](http://evil)",
    "details": "https://knaben.xyz/thepiratebay/description.php?id=1000001",
    "grabs": 9,
    "hash": "0123456789ABCDEF0123456789ABCDEF01234567",
    "id": "1111111111111111111111111111111111111111",
    "lastSeen": "2026-11-19T23:16:44+00:00",
    "link": None,
    "livePeers": 1,
    "liveSeeders": 6,
    "magnetUrl": (
        "magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567"
        "&dn=Handbook&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337"
    ),
    "peers": 0,
    "score": None,
    "seeders": 10,
    "title": "The Example Handbook by Ren&eacute; Author EPUB",
    "tracker": "The Pirate Bay",
    "trackerId": "thepiratebay",
    "virusDetection": 0.33,
}


@pytest.fixture
def provider():
    return KnabenProvider()


@pytest.fixture
def result(provider):
    return provider._parse_torrent(HIT)


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        response = mock.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"hits": [HIT]}).encode()
        yield mock


class TestParseTorrent:
    def test_result(self, result):
        assert result.title == "The Example Handbook by René Author EPUB"
        assert result.info_hash == HIT["hash"].lower()
        assert result.magnet_link == HIT["magnetUrl"]
        assert result.torrent_link is None
        assert result.page_url == HIT["details"]
        assert result.categories == (StandardCategories.BOOKS_EBOOK,)
        assert result.seeders == 10
        assert result.leechers == 0
        assert result.downloads == 9
        assert result.size == 5922042
        assert result.upload_date.year == 2023

    def test_missing_hash_is_skipped(self, provider):
        assert provider._parse_torrent({**HIT, "hash": None}) is None

    def test_missing_title_is_skipped(self, provider):
        assert provider._parse_torrent({**HIT, "title": None}) is None

    def test_invalid_hit_is_skipped(self, provider):
        assert provider._parse_torrent("hit") is None

    def test_missing_magnet_is_built(self, provider):
        result = provider._parse_torrent({**HIT, "magnetUrl": None})

        assert result.magnet_link.startswith(
            "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
        )

    @pytest.mark.parametrize(
        "magnet",
        [
            "magnet:?xt=urn:btih:" + "f" * 40,
            # Hash with extra characters
            "magnet:?xt=urn:btih:0123456789ABCDEF0123456789ABCDEF01234567ff",
        ],
    )
    def test_magnet_for_other_torrent_is_rebuilt(self, provider, magnet):
        result = provider._parse_torrent({**HIT, "magnetUrl": magnet})

        assert result.magnet_link.startswith(
            "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&"
        )

    def test_invalid_date_is_ignored(self, provider):
        result = provider._parse_torrent({**HIT, "date": 123})

        assert result.upload_date is None

    @pytest.mark.parametrize(
        "category_ids, expected",
        [
            ([9001000, 9000000], [StandardCategories.BOOKS_EBOOK]),
            ([4004000, 4000000], [StandardCategories.PC_ISO]),  # PC/Unix
            # Anime/Music is in Audio too
            (
                [6007000, 6000000, 1000000],
                [StandardCategories.AUDIO_OTHER, StandardCategories.TV_ANIME],
            ),
            # Deeper ID is mapped by subcategory (XXX/Hentai/Games)
            ([5004003, 5004000], [StandardCategories.XXX_OTHER]),
            ([1000000, 1001045], [StandardCategories.AUDIO_MP3]),  # genre
            # Anime results are often in Movies/Other too
            (
                [3000000, 3008000, 6000000, 6001000],
                [
                    StandardCategories.MOVIES_OTHER,
                    StandardCategories.TV_ANIME,
                ],
            ),
            # TV is dropped as Anime is more specific
            ([2000000, 6000000], [StandardCategories.TV_ANIME]),
            ([10000000], [StandardCategories.OTHER]),
            ([99000000], []),
            (None, []),
        ],
    )
    def test_categories(self, provider, category_ids, expected):
        assert provider._get_categories(category_ids) == expected


class TestDetails:
    def test_details(self, provider, result):
        fields = details_fields(provider.details_extended(result))

        assert fields["Tracker"] == "The Pirate Bay"
        assert fields["Category"] == "Books / EBooks"
        assert fields["Live Seeders"] == "6"
        # UTC date is shown in local time
        last_seen = datetime.fromisoformat(HIT["lastSeen"]).astimezone()
        assert fields["Last Seen"] == last_seen.strftime("%Y-%m-%d %H:%M")

    def test_description_is_text(self, provider, result):
        sections = provider.details_extended(result)

        assert details_section(sections, "Description").text == (
            "Uploader: uploader1\nRené [x](http://evil)"
        )

    def test_description_same_as_title_is_hidden(self, provider):
        result = provider._parse_torrent({**HIT, "description": HIT["title"]})
        sections = provider.details_extended(result)

        assert details_section(sections, "Description") is None


class TestSearch:
    def test_empty_query(self, provider, mock_urlopen):
        assert provider.search("  ") == []
        mock_urlopen.assert_not_called()

    def test_search_request(self, provider, mock_urlopen):
        results = provider.search(" example ")

        url = mock_urlopen.call_args.args[0]
        assert url.startswith("https://api.knaben.org/v2/search?q=example&")
        assert "o=seeders" in url
        assert "c=" not in url
        assert url.endswith("&xxx")
        assert len(results) == 1

    @pytest.mark.parametrize(
        "categories, expected",
        [
            (None, []),
            ([StandardCategories.MOVIES], [3000000]),
            ([StandardCategories.MOVIES_UHD], [3000000]),
            ([StandardCategories.TV], [2000000, 6000000]),
            ([StandardCategories.PC_GAMES], [4000000, 8000000]),
            (
                [StandardCategories.BOOKS, StandardCategories.CONSOLE],
                [7000000, 9000000],
            ),
        ],
    )
    def test_convert(self, provider, categories, expected):
        assert provider._convert_categories_to_knaben(categories) == expected

    def test_search_request_categories(self, provider, mock_urlopen):
        provider.search("example", [StandardCategories.TV])

        url = mock_urlopen.call_args.args[0]
        assert "c=2000000%2C6000000" in url
        assert "xxx" not in url

    def test_search_request_xxx_category(self, provider, mock_urlopen):
        provider.search("example", [StandardCategories.XXX])

        url = mock_urlopen.call_args.args[0]
        assert "c=5000000" in url
        assert url.endswith("&xxx")

    def test_invalid_response(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b"not json"

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("example")

    @pytest.mark.parametrize("data", [[], {}, {"hits": "x"}])
    def test_invalid_hits(self, provider, mock_urlopen, data):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(data).encode()

        with pytest.raises(Exception, match="invalid hits"):
            provider.search("example")

    def test_invalid_hit_does_not_fail_search(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"hits": ["x", {**HIT, "hash": "B" * 40, "title": ["x"]}, HIT]}
        ).encode()

        results = provider.search("example")

        assert [r.info_hash for r in results] == [HIT["hash"].lower()]


class TestCounts:
    """Counts are passed from JSON as received, which could be text."""

    def test_digit_strings_are_converted(self, provider):
        result = provider._parse_torrent(
            {**HIT, "seeders": "1", "peers": "2", "grabs": "3", "bytes": "4"}
        )
        assert (
            result.seeders,
            result.leechers,
            result.downloads,
            result.size,
        ) == (
            1,
            2,
            3,
            4,
        )

    @pytest.mark.parametrize("value", ["[@click=app.pwn()]1[/]", "-1", None])
    def test_invalid_values_are_none(self, provider, value):
        result = provider._parse_torrent(
            {
                **HIT,
                "seeders": value,
                "peers": value,
                "grabs": value,
                "bytes": value,
            }
        )
        assert (
            result.seeders,
            result.leechers,
            result.downloads,
            result.size,
        ) == (
            None,
            None,
            None,
            None,
        )
