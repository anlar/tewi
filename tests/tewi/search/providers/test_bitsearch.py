"""Unit tests for Bitsearch provider (without Bitsearch)."""

import json
import urllib.error
from unittest.mock import patch

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.bitsearch import BitsearchProvider
from tests.tewi.search.helpers import details_fields, details_section

SEARCH_TORRENT = {
    "id": "6ae9ad00f20355a4b00411aa",
    "infohash": "7ACF8FB590B2060DD9C3146EF770169D593433B0",
    "title": "debian-13.7.0-amd64-netinst.iso",
    "size": 792723456,
    "category": 5,
    "subCategory": 4,
    "seeders": 274,
    "leechers": 26,
    "verified": False,
    "createdAt": "2026-11-03T09:44:32.672Z",
}

DETAILS = {
    "success": True,
    "torrent": {
        "id": "6ae9ad00f20355a4b00411aa",
        "tags": ["debian", "[x](http://evil)"],
        "downloads": 898,
        "files": [
            {"path": "debian.iso", "size": 1024},
            {"path": "# README"},
        ],
        "trackers": ["DHT", "udp://tracker.example.org:1337/announce"],
    },
}


@pytest.fixture
def provider():
    return BitsearchProvider()


@pytest.fixture
def result(provider):
    return provider._parse_torrent(SEARCH_TORRENT)


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        response = mock.return_value.__enter__.return_value
        response.read.return_value = json.dumps(DETAILS).encode()
        yield mock


class TestDetails:
    def test_details_request(self, provider, result, mock_urlopen):
        provider.details_extended(result)

        url = mock_urlopen.call_args.args[0]
        assert url == (
            "https://bitsearch.eu/api/v1/torrent/6ae9ad00f20355a4b00411aa"
        )

    def test_details_content(self, provider, result, mock_urlopen):
        sections = provider.details_extended(result)
        fields = details_fields(sections)

        assert fields["Category"] == "Softwares"
        assert fields["Subcategory"] == "Linux"
        assert fields["Downloads"] == "898"
        assert details_section(sections, "Files (2)").items == (
            "debian.iso (1.02 kB)",
            "# README",
        )
        # "DHT" isn't tracker URL
        assert details_section(sections, "Trackers").items == (
            "udp://tracker.example.org:1337/announce",
        )

    def test_remote_text_is_kept_as_is(self, provider, result, mock_urlopen):
        fields = details_fields(provider.details_extended(result))

        assert fields["Tags"] == "debian, [x](http://evil)"

    def test_files_list_is_limited(self, provider, result, mock_urlopen):
        files = [{"path": f"f{i}"} for i in range(150)]
        details = {"success": True, "torrent": {"files": files}}
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(details).encode()

        sections = provider.details_extended(result)
        items = details_section(sections, "Files (150)").items

        assert len(items) == 101
        assert items[99] == "f99"
        assert items[-1] == "...and 50 more"

    def test_invalid_remote_values_are_skipped(
        self, provider, result, mock_urlopen
    ):
        details = {
            "success": True,
            "torrent": {
                "downloads": "many",
                "files": [{"path": "a", "size": "big"}],
            },
        }
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(details).encode()

        sections = provider.details_extended(result)

        assert "Downloads" not in details_fields(sections)
        assert details_section(sections, "Files (1)").items == ("a",)

    def test_network_error_keeps_basic_details(
        self, provider, result, mock_urlopen
    ):
        mock_urlopen.side_effect = urllib.error.URLError("down")

        sections = provider.details_extended(result)

        assert details_fields(sections)["Category"] == "Softwares"
        assert [s.title for s in sections] == ["Information"]


class TestParseTorrent:
    def test_result(self, result):
        assert result.page_url == (
            "https://bitsearch.eu/torrent/6ae9ad00f20355a4b00411aa"
        )
        assert result.categories == (StandardCategories.PC,)
        assert result.upload_date.year == 2026
        # Search always returns 0 downloads, so they are unknown
        assert result.downloads is None

    def test_missing_id_is_skipped(self, provider):
        assert provider._parse_torrent({**SEARCH_TORRENT, "id": None}) is None

    def test_invalid_date_is_ignored(self, provider):
        result = provider._parse_torrent({**SEARCH_TORRENT, "createdAt": 123})

        assert result.upload_date is None

    @pytest.mark.parametrize(
        "cat, sub_cat, expected",
        [
            (6, 5, StandardCategories.CONSOLE),  # Games/PlayStation
            (6, 1, StandardCategories.PC_GAMES),  # Games/PC
            (6, 99, StandardCategories.PC_GAMES),  # unknown subcategory
            (5, 4, StandardCategories.PC),  # Software/Linux
            (2, 2, StandardCategories.MOVIES_UHD),
            (1, 2, StandardCategories.MOVIES),  # Other/Video
            (1, 18, StandardCategories.OTHER),  # Other/Subtitles
            (99, None, None),
        ],
    )
    def test_category(self, provider, cat, sub_cat, expected):
        assert provider.get_category(cat, sub_cat) == expected


class TestCategoryFilter:
    @pytest.mark.parametrize(
        "categories, expected",
        [
            (None, []),
            ([StandardCategories.MOVIES], [2]),
            ([StandardCategories.BOOKS], [9]),
            ([StandardCategories.OTHER], [1]),
            ([StandardCategories.CONSOLE], [6]),
            ([StandardCategories.MOVIES_UHD], [2]),
            ([StandardCategories.PC], [5, 6]),
            ([StandardCategories.TV], [3, 4]),
            ([StandardCategories.MOVIES, StandardCategories.TV], [2, 3, 4]),
            ([StandardCategories.CONSOLE, StandardCategories.PC_GAMES], [5, 6]),
            # Too many categories to search separately
            (
                [
                    StandardCategories.MOVIES,
                    StandardCategories.PC,
                    StandardCategories.BOOKS,
                ],
                [],
            ),
        ],
    )
    def test_convert(self, provider, categories, expected):
        assert provider._convert_categories_to_bs(categories) == expected

    def test_search_request(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"success": true, "results": []}'

        provider.search("example", [StandardCategories.MOVIES])

        url = mock_urlopen.call_args.args[0]
        assert "category=2" in url
        assert "subCategory" not in url

    def test_search_request_per_category(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"success": True, "results": [SEARCH_TORRENT]}
        ).encode()

        results = provider.search("example", [StandardCategories.TV])

        urls = [c.args[0] for c in mock_urlopen.call_args_list]
        assert len(urls) == 2
        assert "category=3" in urls[0]
        assert "category=4" in urls[1]
        assert len(results) == 2

    def test_search_request_all_categories(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"success": true, "results": []}'

        provider.search("example")

        url = mock_urlopen.call_args.args[0]
        assert "category" not in url


class TestCounts:
    """Counts are passed from JSON as received, which could be text."""

    def test_digit_strings_are_converted(self, provider):
        result = provider._parse_torrent(
            {**SEARCH_TORRENT, "seeders": "1", "leechers": "2", "size": "3"}
        )
        assert (
            result.seeders,
            result.leechers,
            result.size,
        ) == (
            1,
            2,
            3,
        )

    @pytest.mark.parametrize("value", ["[@click=app.pwn()]1[/]", "-1", None])
    def test_invalid_values_are_none(self, provider, value):
        result = provider._parse_torrent(
            {
                **SEARCH_TORRENT,
                "seeders": value,
                "leechers": value,
                "size": value,
            }
        )
        assert (
            result.seeders,
            result.leechers,
            result.size,
        ) == (
            None,
            None,
            None,
        )
