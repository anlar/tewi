# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for TheRARBG provider (without TheRARBG)."""

import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from src.tewi.search.models import DetailsLink, StandardCategories
from src.tewi.search.providers.therarbg import TheRarbgProvider
from tests.tewi.search.helpers import details_fields, details_section

HASH_JSON = "0123456789ABCDEF0123456789ABCDEF01234567"
HASH_RSS = "fedcba9876543210fedcba9876543210fedcba98"

JSON_TORRENT = {
    "pk": "a00001",
    "n": "Example Show S04 Season 4 2025 1080p WEBRip",
    "a": 1761826864,
    "c": "TV",
    "s": 6000000000,
    "t": None,
    "u": "uploader1",
    "se": 278,
    "le": 87,
    "i": "tt0000001",
    "h": HASH_JSON,
    "tg": ["1080p", "[x](http://evil)"],
}

FUZZY_TORRENT = {
    **JSON_TORRENT,
    "pk": "1",
    "n": "Sample 2022 1080p",
    "h": "B" * 40,
}

SEARCH = {
    "links": {"next": None, "previous": None},
    "page_size": 100,
    "count": 2,
    "total": 2,
    "results": [JSON_TORRENT, FUZZY_TORRENT],
}


def rss_item(
    info_hash: str = HASH_RSS,
    title: str = "Example Guide",
    category: str = "Books",
) -> str:
    return f"""
<item>
  <title>{title}</title>
  <link>https://therarbg.com/post-detail/a00002/example-guide/</link>
  <guid isPermaLink="false">{info_hash}</guid>
  <pubDate>Mon, 08 Apr 2024 18:42:59 +0000</pubDate>
  <description>122.4 MB - 3 seeders - quality 0/100</description>
  <category>{category}</category>
  <enclosure url="magnet:?xt=urn:btih:{info_hash}" length="128398131"
    type="application/x-bittorrent" />
</item>"""


def rss(*items: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<rss version="2.0"><channel>{"".join(items)}</channel></rss>'
    ).encode()


DETAILS = {
    "eid": "a00001",
    "downloads": 1234,
    "language": "English",
    "imdb": "tt0000001",
    "last_checked": "2026-11-18T22:59:25.892732Z",
    "num_files": 0,
    "files": [
        {"name": "e1.mkv", "size": 1024, "full_location": "S04/e1.mkv"},
        {"name": "# README", "size": None, "full_location": None},
    ],
    "trackers": [
        {
            "tracker": "udp://tracker.example.org:1337",
            "seeders": 5,
            "leechers": 2,
        },
        {"tracker": "udp://dead.example.org:80"},
    ],
}


@pytest.fixture
def provider():
    return TheRarbgProvider()


@pytest.fixture
def result(provider):
    return provider._parse_torrent(JSON_TORRENT)


def mock_responses(mock, json_data=SEARCH, rss_data: bytes | None = None):
    """Return JSON search and RSS feed responses by requested URL."""
    if rss_data is None:
        rss_data = rss()

    def urlopen(url, **kwargs):
        response = mock.return_value.__enter__.return_value
        if "/api/rss/" in url:
            response.read.return_value = rss_data
        else:
            response.read.return_value = json.dumps(json_data).encode()
        return mock.return_value

    mock.side_effect = urlopen


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        mock_responses(mock)
        yield mock


def request_params(mock, index: int) -> dict[str, list[str]]:
    return parse_qs(urlparse(mock.call_args_list[index].args[0]).query)


class TestSearch:
    def test_empty_query(self, provider, mock_urlopen):
        assert provider.search("  ") == []
        mock_urlopen.assert_not_called()

    def test_requests(self, provider, mock_urlopen):
        provider.search(" example ")

        json_url = mock_urlopen.call_args_list[0].args[0]
        assert json_url.startswith("https://therarbg.com/get-posts/?")
        assert request_params(mock_urlopen, 0) == {
            "keywords": ["example"],
            "format": ["json"],
            "order": ["-se"],
            "page_size": ["100"],
        }
        rss_url = mock_urlopen.call_args_list[1].args[0]
        assert rss_url.startswith("https://therarbg.com/api/rss/search/?")
        assert request_params(mock_urlopen, 1) == {
            "q": ["example"],
            "limit": ["100"],
        }

    def test_fuzzy_matches_are_removed(self, provider, mock_urlopen):
        results = provider.search("example")

        assert [r.info_hash for r in results] == [HASH_JSON.lower()]

    def test_rss_results_are_merged(self, provider, mock_urlopen):
        mock_responses(
            mock_urlopen,
            rss_data=rss(rss_item(HASH_JSON.lower()), rss_item()),
        )

        results = provider.search("example")

        # JSON result is kept for duplicate, as it has leechers
        assert [r.info_hash for r in results] == [HASH_JSON.lower(), HASH_RSS]
        assert results[0].leechers == 87

    def test_rss_failure_is_ignored(self, provider, mock_urlopen):
        mock_responses(mock_urlopen, rss_data=b"not xml")

        results = provider.search("example")

        assert [r.info_hash for r in results] == [HASH_JSON.lower()]

    def test_invalid_results_are_raised(self, provider, mock_urlopen):
        mock_responses(mock_urlopen, json_data={"results": "x"})

        with pytest.raises(Exception, match="invalid results"):
            provider.search("example")

    def test_invalid_result_is_skipped(self, provider, mock_urlopen):
        mock_responses(
            mock_urlopen,
            json_data={
                "results": [
                    "x",
                    {**JSON_TORRENT, "h": "C" * 40, "n": ["example"]},
                    JSON_TORRENT,
                ]
            },
        )

        results = provider.search("example")

        assert [r.info_hash for r in results] == [HASH_JSON.lower()]

    def test_json_failure_is_raised(self, provider, mock_urlopen):
        mock_urlopen.side_effect = None
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b"not json"

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("example")


class TestCategoryFilter:
    @pytest.mark.parametrize(
        "categories, expected",
        [
            (None, []),
            ([StandardCategories.MOVIES], ["Movies"]),
            ([StandardCategories.MOVIES_UHD], ["Movies"]),
            ([StandardCategories.TV], ["Anime", "Documentaries", "TV"]),
            ([StandardCategories.PC_GAMES], ["Apps", "Games"]),
            (
                [StandardCategories.CONSOLE, StandardCategories.BOOKS],
                ["Books", "Games"],
            ),
        ],
    )
    def test_convert(self, provider, categories, expected):
        assert provider._convert_categories_to_rarbg(categories) == expected

    def test_single_category_request(self, provider, mock_urlopen):
        provider.search("example", [StandardCategories.MOVIES])

        assert request_params(mock_urlopen, 0)["category"] == ["Movies"]
        assert request_params(mock_urlopen, 1)["category"] == ["Movies"]

    def test_several_categories_request(self, provider, mock_urlopen):
        mock_responses(mock_urlopen, rss_data=rss(rss_item("C" * 40)))

        results = provider.search("example", [StandardCategories.TV])

        # Site filters by last category only, so each one is searched
        categories = [
            request_params(mock_urlopen, i)["category"] for i in range(6)
        ]
        assert categories == [["Anime"], ["Documentaries"], ["TV"]] * 2
        assert mock_urlopen.call_count == 6
        # Duplicates from several requests are merged
        assert [r.info_hash for r in results] == [HASH_JSON.lower(), "c" * 40]


class TestParse:
    def test_json_result(self, result):
        assert result.title == JSON_TORRENT["n"]
        assert result.info_hash == HASH_JSON.lower()
        assert result.magnet_link.startswith(
            f"magnet:?xt=urn:btih:{HASH_JSON.lower()}"
        )
        assert "&tr=udp://tracker.therarbg.to:6969/announce" in (
            result.magnet_link
        )
        assert result.categories == (StandardCategories.TV,)
        assert result.seeders == 278
        assert result.leechers == 87
        assert result.size == 6000000000
        assert result.upload_date.year == 2025
        assert result.page_url == (
            "https://therarbg.com/post-detail/a00001/"
            "example-show-s04-season-4-2025-1080p-webrip/"
        )
        assert result.extra["tags"] == "1080p, [x](http://evil)"

    def test_json_result_without_hash_is_skipped(self, provider):
        assert provider._parse_torrent({**JSON_TORRENT, "h": None}) is None

    def test_json_result_with_invalid_hash_is_skipped(self, provider):
        torrent = {**JSON_TORRENT, "h": "x&tr=http://evil"}

        assert provider._parse_torrent(torrent) is None

    def test_rss_result(self, provider, mock_urlopen):
        mock_responses(
            mock_urlopen, json_data={"results": []}, rss_data=rss(rss_item())
        )

        [result] = provider.search("example")

        assert result.info_hash == HASH_RSS
        assert result.categories == (StandardCategories.BOOKS,)
        assert result.seeders == 3
        assert result.leechers is None
        assert result.size == 128398131
        assert result.upload_date.year == 2024
        assert result.extra["torrent_id"] == "a00002"

    def test_rss_result_without_size(self, provider, mock_urlopen):
        item = rss_item().replace('length="128398131"', "")
        mock_responses(
            mock_urlopen, json_data={"results": []}, rss_data=rss(item)
        )

        [result] = provider.search("example")

        assert result.size is None

    @pytest.mark.parametrize(
        "category, expected",
        [
            ("Games", StandardCategories.PC_GAMES),
            ("Anime", StandardCategories.TV_ANIME),
            ("Documentaries", StandardCategories.TV_DOCUMENTARY),
            ("Apps", StandardCategories.PC),
            ("TV shows", StandardCategories.TV),
            ("E-books", StandardCategories.BOOKS_EBOOK),
        ],
    )
    def test_category(self, provider, category, expected):
        assert provider._get_categories(category) == (expected,)

    def test_unknown_category(self, provider):
        assert provider._get_categories("Unknown") == ()


class TestDetails:
    @pytest.fixture
    def mock_details(self):
        with patch("src.tewi.search.base._urlopen") as mock:
            response = mock.return_value.__enter__.return_value
            response.read.return_value = json.dumps(DETAILS).encode()
            yield mock

    def test_details_request(self, provider, result, mock_details):
        provider.details_extended(result)

        url = mock_details.call_args.args[0]
        assert url == ("https://therarbg.com/post-detail/a00001/x/?format=json")

    def test_details_content(self, provider, result, mock_details):
        sections = provider.details_extended(result)
        fields = details_fields(sections)

        assert fields["Category"] == "TV"
        assert fields["Uploader"] == "uploader1"
        assert fields["Downloads"] == "1234"
        assert fields["Language"] == "English"
        assert fields["IMDB"] == DetailsLink(
            "https://www.imdb.com/title/tt0000001/"
        )
        assert fields["Last Checked"] == "2026-11-18 22:59"
        # File count from list, as num_files could be 0
        assert details_section(sections, "Files (2)").items == (
            "S04/e1.mkv (1.02 kB)",
            "# README",
        )
        assert details_section(sections, "Trackers").items == (
            "udp://tracker.example.org:1337 (5 seeders, 2 leechers)",
            "udp://dead.example.org:80",
        )

    def test_invalid_imdb_is_skipped(self, provider, result, mock_details):
        response = mock_details.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {**DETAILS, "imdb": "tt1 [x](http://evil)"}
        ).encode()

        sections = provider.details_extended(result)

        assert "IMDB" not in details_fields(sections)

    def test_details_failure(self, provider, result, mock_details):
        response = mock_details.return_value.__enter__.return_value
        response.read.return_value = b"not json"

        sections = provider.details_extended(result)

        assert details_fields(sections)["Category"] == "TV"
        assert [s.title for s in sections] == ["Information"]


class TestCounts:
    """Counts are passed from JSON as received, which could be text."""

    def test_digit_strings_are_converted(self, provider):
        result = provider._parse_torrent(
            {**JSON_TORRENT, "se": "1", "le": "2", "s": "3"}
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
            {**JSON_TORRENT, "se": value, "le": value, "s": value}
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
