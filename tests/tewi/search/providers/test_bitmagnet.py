# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Bitmagnet provider (without Bitmagnet)."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.bitmagnet import BitmagnetProvider
from tests.tewi.search.helpers import details_fields, details_section

HASH = "0123456789abcdef0123456789abcdef01234567"


def item(**kwargs) -> dict:
    return {
        "infoHash": HASH,
        "contentType": "tv_show",
        "contentSource": "tmdb",
        "contentId": "1001",
        "languages": [{"name": "English"}, {"name": "Japanese"}],
        "episodes": {"label": "S01E01-E05, S03"},
        "videoResolution": "V1080p",
        "releaseGroup": "Group",
        "seeders": 12,
        "leechers": 3,
        "publishedAt": "2026-11-01T10:00:00.123456Z",
        "createdAt": "2026-11-02T10:00:00Z",
        "updatedAt": "2026-11-03T10:00:00Z",
        "torrent": {
            "name": "Example Show S01",
            "size": 1024,
            "seeders": 20,
            "leechers": 5,
            "filesCount": 3,
            "magnetUri": f"magnet:?xt=urn:btih:{HASH}&tr=udp://t.example",
            "fileTypes": ["video"],
            "tagNames": [],
            "createdAt": "2026-11-02T10:00:00Z",
            "updatedAt": "2026-11-03T10:00:00Z",
            "sources": [
                {"key": "dht", "name": "DHT", "seeders": 12, "leechers": 3},
                {"key": "x", "name": None},
            ],
        },
        **kwargs,
    }


def search(*items: dict) -> dict:
    return {"data": {"torrentContent": {"search": {"items": list(items)}}}}


DETAILS = {
    "data": {
        "torrentContent": {
            "search": {
                "items": [
                    {
                        "content": {
                            "title": "Example Show",
                            "overview": "Long overview",
                            "releaseYear": 2025,
                            "runtime": 24,
                            "voteAverage": 7.25,
                            "voteCount": 100,
                            "originalLanguage": {"name": "Japanese"},
                            "externalLinks": [
                                {
                                    "metadataSource": {"name": "TMDB"},
                                    "url": "https://www.themoviedb.org/tv/1",
                                },
                                {"metadataSource": {"name": "X"}, "url": None},
                            ],
                        }
                    }
                ]
            }
        },
        "torrent": {
            "files": {
                "items": [
                    {"path": "Show/e1.mkv", "size": 1000},
                    {"path": "Show/e2.mkv", "size": None},
                ],
            }
        },
    }
}


@pytest.fixture
def provider():
    return BitmagnetProvider("http://bitmagnet:3333/")


@pytest.fixture
def mock_post():
    with patch("src.tewi.search.base._urlopen_post") as mock:
        set_response(mock, search(item()))
        yield mock


def set_response(mock, data: dict) -> None:
    response = mock.return_value.__enter__.return_value
    response.read.return_value = json.dumps(data).encode()


def request(mock, index: int = -1) -> dict:
    call = mock.call_args_list[index]
    assert call.args[0] == "http://bitmagnet:3333/graphql"
    return json.loads(call.kwargs["data"])


class TestSearch:
    def test_not_configured(self):
        with pytest.raises(Exception, match="Bitmagnet URL not configured"):
            BitmagnetProvider(None).search("example")

    def test_empty_query(self, provider, mock_post):
        assert provider.search("  ") == []
        mock_post.assert_not_called()

    def test_request(self, provider, mock_post):
        provider.search(" example ")

        assert request(mock_post)["variables"] == {
            "query": "example",
            "limit": 100,
            "facets": None,
        }

    @pytest.mark.parametrize(
        "categories, expected",
        [
            ([StandardCategories.MOVIES_HD], ["movie"]),
            ([StandardCategories.AUDIO], ["music", "audiobook"]),
            ([StandardCategories.BOOKS], ["ebook", "comic"]),
            ([StandardCategories.PC], ["game", "software"]),
            # Unknown content type is Other
            ([StandardCategories.OTHER], [None]),
            (
                [StandardCategories.TV, StandardCategories.XXX],
                ["tv_show", "xxx"],
            ),
        ],
    )
    def test_content_type_filter(
        self, provider, mock_post, categories, expected
    ):
        provider.search("example", categories)

        facets = request(mock_post)["variables"]["facets"]
        assert facets == {"contentType": {"filter": expected}}

    def test_unsupported_category_is_not_requested(self, provider, mock_post):
        assert provider.search("example", [StandardCategories.CONSOLE]) == []
        mock_post.assert_not_called()

    def test_result(self, provider, mock_post):
        [result] = provider.search("example")

        assert result.title == "Example Show S01"
        assert result.info_hash == HASH
        assert result.magnet_link == item()["torrent"]["magnetUri"]
        assert result.categories == (StandardCategories.TV,)
        assert (result.seeders, result.leechers) == (12, 3)
        assert (result.size, result.files_count) == (1024, 3)
        assert result.upload_date.year == 2026
        assert result.page_url == (
            f"http://bitmagnet:3333/webui/torrents/permalink/{HASH}"
        )

    def test_fields(self, provider, mock_post):
        [result] = provider.search("example")

        created = datetime.fromisoformat("2026-11-02T10:00:00+00:00")
        assert result.extra == {
            "content_type": "tv_show",
            "content_source": "tmdb",
            "content_id": "1001",
            "release_group": "Group",
            "video_resolution": "V1080p",
            "file_types": "video",
            "languages": "English, Japanese",
            "episodes": "S01E01-E05, S03",
            "sources": "DHT (S:12/L:3), x",
            "item_created_at": f"{created.astimezone():%Y-%m-%d %H:%M}",
            "item_updated_at": result.extra["item_updated_at"],
            "torrent_created_at": f"{created.astimezone():%Y-%m-%d %H:%M}",
            "torrent_updated_at": result.extra["torrent_updated_at"],
        }

    @pytest.mark.parametrize(
        "content_type, expected",
        [
            ("game", StandardCategories.PC_GAMES),
            ("ebook", StandardCategories.BOOKS_EBOOK),
            (None, StandardCategories.OTHER),
        ],
    )
    def test_category(self, provider, mock_post, content_type, expected):
        set_response(mock_post, search(item(contentType=content_type)))

        [result] = provider.search("example")

        assert result.categories == (expected,)

    def test_torrent_peers_are_used_if_item_has_none(self, provider, mock_post):
        set_response(mock_post, search(item(seeders=None, leechers=0)))

        [result] = provider.search("example")

        assert (result.seeders, result.leechers) == (20, 0)

    def test_invalid_item_does_not_fail_search(self, provider, mock_post):
        set_response(
            mock_post,
            search(
                "x",
                item(infoHash="b" * 40, contentType=["x"]),
                item(infoHash="c" * 40, torrent=None),
                item(),
            ),
        )

        assert [r.info_hash for r in provider.search("example")] == [HASH]

    def test_graphql_error(self, provider, mock_post):
        set_response(mock_post, {"errors": [{"message": "bad query"}, "x"]})

        with pytest.raises(Exception, match="GraphQL error: bad query; x"):
            provider.search("example")

    @pytest.mark.parametrize("data", [{}, {"data": None}, {"data": []}])
    def test_invalid_response(self, provider, mock_post, data):
        set_response(mock_post, data)

        with pytest.raises(Exception, match="no items"):
            provider.search("example")


class TestDetails:
    @pytest.fixture
    def result(self, provider, mock_post):
        [result] = provider.search("example")
        set_response(mock_post, DETAILS)
        return result

    def test_request(self, provider, result, mock_post):
        provider.details_extended(result)

        assert request(mock_post)["variables"] == {
            "infoHash": HASH,
            "filesLimit": 100,
        }

    def test_content(self, provider, result):
        sections = provider.details_extended(result)

        assert [s.title for s in sections] == [
            "Content",
            "Overview",
            "Video",
            "Release",
            "Links",
            "Files (3)",
            "Timestamps",
        ]
        fields = details_fields(sections)
        assert fields["Title"] == "Example Show"
        assert fields["Runtime"] == "24 min"
        assert fields["Rating"] == "7.2/10 (100 votes)"
        assert fields["Episodes"] == "S01E01-E05, S03"
        assert details_section(sections, "Overview").text == "Long overview"
        # Total is from search result, as files query is limited
        assert details_section(sections, "Files (3)").items == (
            "Show/e1.mkv (1 kB)",
            "Show/e2.mkv",
            "...and 1 more",
        )

    def test_details_are_cached(self, provider, result, mock_post):
        mock_post.reset_mock()
        first = provider.details_extended(result)
        second = provider.details_extended(result)

        assert mock_post.call_count == 1
        assert second == first

    def test_offline_details_need_download(self, provider, result):
        assert provider.details_extended_offline(result) is None

    def test_offline_details_are_cached(self, provider, result, mock_post):
        loaded = provider.details_extended(result)
        mock_post.reset_mock()

        assert provider.details_extended_offline(result) == loaded
        assert mock_post.call_count == 0

    def test_failure_keeps_basic_details(self, provider, result, mock_post):
        set_response(mock_post, {"errors": [{"message": "failed"}]})

        sections = provider.details_extended(result)

        assert [s.title for s in sections] == [
            "Content",
            "Video",
            "Release",
            "Timestamps",
        ]
