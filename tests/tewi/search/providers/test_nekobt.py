# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for nekoBT provider (without nekoBT)."""

import io
import json
import urllib.error
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from src.tewi.search.models import DetailsLink, StandardCategories
from src.tewi.search.providers.nekobt import NekoBtProvider
from tests.tewi.search.helpers import details_fields, details_section

HASH = "0123456789abcdef0123456789abcdef01234567"
MAGNET = f"magnet:?xt=urn:btih:{HASH}&dn=Example&tr=udp://t.example"


def torrent(**kwargs) -> dict:
    return {
        "id": "1000001",
        "uploaded_at": 1789156573473,
        "title": "[Group] Example Show - 01 (1080p)",
        "infohash": HASH,
        "magnet": MAGNET,
        "media_id": "s1001",
        "filesize": "8423228390",
        "audio_lang": "ja,en",
        "sub_lang": "en,de",
        "fsub_lang": "en",
        "anonymous": False,
        "uploader": {"display_name": "uploader1"},
        "groups": [
            {"display_name": "Group"},
            {"display_name": "[x](http://evil)"},
        ],
        "seeders": "46",
        "leechers": "2",
        "completed": "803",
        "batch": True,
        "deleted": None,
        "hidden": False,
        **kwargs,
    }


def search(*torrents: dict) -> dict:
    return {"error": False, "data": {"results": list(torrents), "more": False}}


TORRENT_DETAILS = {
    "error": False,
    "data": {
        "id": "1000001",
        "anilist_id": 2001,
        "files": [
            {"path": "Example/Example - 01.mkv", "length": 1000},
            {"path": "# README"},
        ],
        "description": "## Remote [link](http://evil)",
        "mediainfo": "General\nUnique ID : 1",
    },
}

MEDIA_DETAILS = {
    "error": False,
    "data": {
        "id": "s1001",
        "tvdbId": 3001,
        "tmdbId": 4001,
        "imdbId": "tt0000001",
    },
}


def set_responses(
    mock,
    search_data: dict | bytes | None = None,
    torrent_data: dict | bytes = TORRENT_DETAILS,
    media_data: dict | bytes = MEDIA_DETAILS,
) -> None:
    """Return responses by requested URL."""
    if search_data is None:
        search_data = search(torrent())
    response = mock.return_value.__enter__.return_value

    def encode(data: dict | bytes) -> bytes:
        return data if isinstance(data, bytes) else json.dumps(data).encode()

    def urlopen(url, **kwargs):
        if "/torrents/search?" in url:
            response.read.return_value = encode(search_data)
        elif "/torrents/" in url:
            response.read.return_value = encode(torrent_data)
        elif "/media/" in url:
            response.read.return_value = encode(media_data)
        return mock.return_value

    mock.side_effect = urlopen


@pytest.fixture
def provider():
    return NekoBtProvider()


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        set_responses(mock)
        yield mock


def request_params(mock, index: int = 0) -> dict[str, list[str]]:
    return parse_qs(urlparse(mock.call_args_list[index].args[0]).query)


class TestSearch:
    def test_empty_query(self, provider, mock_urlopen):
        assert provider.search("  ") == []
        mock_urlopen.assert_not_called()

    def test_request(self, provider, mock_urlopen):
        provider.search(" example show ")

        url = mock_urlopen.call_args.args[0]
        assert url.startswith("https://nekobt.to/api/v1/torrents/search?")
        assert request_params(mock_urlopen) == {
            "query": ["example show"],
            "limit": ["100"],
            "sort_by": ["seeders"],
        }

    def test_result(self, provider, mock_urlopen):
        [result] = provider.search("example")

        assert result.title == "[Group] Example Show - 01 (1080p)"
        assert result.info_hash == HASH
        assert result.magnet_link == MAGNET
        assert result.page_url == "https://nekobt.to/torrents/1000001"
        assert result.categories == (StandardCategories.TV_ANIME,)
        assert result.seeders == 46
        assert result.leechers == 2
        assert result.downloads == 803
        assert result.size == 8423228390
        assert result.upload_date.year == 2026
        assert result.extra["torrent_id"] == "1000001"
        assert result.extra["media_id"] == "s1001"

    def test_api_error(self, provider, mock_urlopen):
        set_responses(
            mock_urlopen, {"error": True, "message": "Something failed."}
        )

        with pytest.raises(Exception, match="API error: Something failed."):
            provider.search("example")

    def test_http_error(self, provider, mock_urlopen):
        body = b'{"error":true,"message":"\'limit\' must be <= 100."}'
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 400, "Bad Request", {}, io.BytesIO(body)
        )

        with pytest.raises(
            Exception, match="API error: HTTP 400: 'limit' must be <= 100."
        ):
            provider.search("example")

    def test_invalid_response(self, provider, mock_urlopen):
        set_responses(mock_urlopen, b"not json")

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("example")

    @pytest.mark.parametrize(
        "data",
        [{"error": False}, {"error": False, "data": {"results": "x"}}],
    )
    def test_invalid_results(self, provider, mock_urlopen, data):
        set_responses(mock_urlopen, data)

        with pytest.raises(Exception, match="invalid results"):
            provider.search("example")

    def test_invalid_torrent_does_not_fail_search(self, provider, mock_urlopen):
        set_responses(
            mock_urlopen,
            search("x", torrent(infohash="b" * 40, title=["x"]), torrent()),
        )

        assert [r.info_hash for r in provider.search("example")] == [HASH]

    def test_upload_date_as_string(self, provider, mock_urlopen):
        set_responses(
            mock_urlopen, search(torrent(uploaded_at="1789156573473"))
        )

        [result] = provider.search("example")

        assert result.upload_date.year == 2026

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"infohash": None},
            {"infohash": "x&tr=http://evil"},
            {"title": ""},
            {"id": "1/../x"},
            {"deleted": True},
            {"hidden": True},
        ],
    )
    def test_invalid_torrent_is_skipped(self, provider, mock_urlopen, kwargs):
        set_responses(mock_urlopen, search(torrent(**kwargs)))

        assert provider.search("example") == []

    @pytest.mark.parametrize(
        "other",
        [
            "magnet:?xt=urn:btih:" + "f" * 40,
            # Hash with extra characters
            f"magnet:?xt=urn:btih:{HASH}ff&tr=udp://t.example",
        ],
    )
    def test_magnet_for_other_torrent_is_rebuilt(
        self, provider, mock_urlopen, other
    ):
        set_responses(mock_urlopen, search(torrent(magnet=other)))

        [result] = provider.search("example")

        assert result.magnet_link.startswith(f"magnet:?xt=urn:btih:{HASH}")
        assert "&tr=" not in result.magnet_link

    def test_missing_optional_fields(self, provider, mock_urlopen):
        data = {"id": "1000001", "title": "Example", "infohash": HASH}
        set_responses(mock_urlopen, search(data))

        [result] = provider.search("example")

        # Torrents without media are anime
        assert result.categories == (StandardCategories.TV_ANIME,)
        assert result.seeders is None
        assert result.size is None
        assert result.upload_date is None
        assert "media_id" not in result.extra


class TestCategories:
    @pytest.fixture
    def mixed(self, mock_urlopen):
        set_responses(
            mock_urlopen,
            search(torrent(), torrent(infohash="b" * 40, media_id="m1002")),
        )

    def test_movie_category(self, provider, mock_urlopen, mixed):
        results = provider.search("example")

        assert [r.categories for r in results] == [
            (StandardCategories.TV_ANIME,),
            (StandardCategories.MOVIES,),
        ]

    def test_movies(self, provider, mock_urlopen, mixed):
        results = provider.search("example", [StandardCategories.MOVIES])

        # Results are filtered by search manager
        assert len(results) == 2
        # Movies are rarely among most seeded torrents
        assert request_params(mock_urlopen)["sort_by"] == ["best"]

    def test_tv_subcategory(self, provider, mock_urlopen, mixed):
        provider.search("example", [StandardCategories.TV_HD])

        assert request_params(mock_urlopen)["sort_by"] == ["seeders"]

    def test_movies_and_tv(self, provider, mock_urlopen, mixed):
        results = provider.search(
            "example", [StandardCategories.MOVIES, StandardCategories.TV]
        )

        assert len(results) == 2
        assert request_params(mock_urlopen)["sort_by"] == ["seeders"]

    def test_unsupported_category_is_not_requested(
        self, provider, mock_urlopen
    ):
        assert provider.search("example", [StandardCategories.AUDIO]) == []
        mock_urlopen.assert_not_called()


class TestDetails:
    @pytest.fixture
    def result(self, provider, mock_urlopen):
        [result] = provider.search("example")
        return result

    def test_requests(self, provider, result, mock_urlopen):
        mock_urlopen.reset_mock()

        provider.details_extended(result)

        urls = [c.args[0] for c in mock_urlopen.call_args_list]
        assert urls == [
            "https://nekobt.to/api/v1/torrents/1000001",
            "https://nekobt.to/api/v1/media/s1001",
        ]

    def test_content(self, provider, result):
        sections = provider.details_extended(result)
        fields = details_fields(sections)

        assert fields["Audio"] == "ja, en"
        assert fields["Subtitles"] == "en, de"
        assert fields["Uploader"] == "uploader1"
        assert fields["Groups"] == "Group, [x](http://evil)"
        assert fields["Batch"] == "Yes"
        assert fields["AniList"] == DetailsLink("https://anilist.co/anime/2001")
        assert fields["TVDB"] == DetailsLink(
            "https://thetvdb.com/dereferrer/series/3001"
        )
        assert fields["TMDB"] == DetailsLink(
            "https://www.themoviedb.org/tv/4001"
        )
        assert fields["IMDB"] == DetailsLink(
            "https://www.imdb.com/title/tt0000001/"
        )
        assert details_section(sections, "Files (2)").items == (
            "Example/Example - 01.mkv (1 kB)",
            "# README",
        )
        # Remote Markdown description and media info aren't shown
        assert "Remote" not in repr(sections)
        assert "Unique ID" not in repr(sections)

    def test_anonymous_uploader(self, provider, mock_urlopen):
        set_responses(mock_urlopen, search(torrent(anonymous=True)))
        [result] = provider.search("example")

        sections = provider.details_extended(result)

        assert details_fields(sections)["Uploader"] == "Anonymous"
        assert "uploader1" not in repr(sections)

    def test_movie_tmdb_link(self, provider, mock_urlopen):
        set_responses(mock_urlopen, search(torrent(media_id="m1002")))
        [result] = provider.search("example")

        fields = details_fields(provider.details_extended(result))

        assert fields["TMDB"] == DetailsLink(
            "https://www.themoviedb.org/movie/4001"
        )

    def test_invalid_ids_are_skipped(self, provider, result, mock_urlopen):
        set_responses(
            mock_urlopen,
            torrent_data={"data": {"anilist_id": "1 [x](http://evil)"}},
            media_data={
                "data": {
                    "tvdbId": None,
                    "tmdbId": "x",
                    "imdbId": "tt1 [x](http://evil)",
                }
            },
        )

        sections = provider.details_extended(result)

        assert details_section(sections, "Links") is None
        assert "anilist.co" not in repr(sections)
        assert "imdb.com" not in repr(sections)

    def test_files_are_limited(self, provider, result, mock_urlopen):
        files = [{"path": f"e{i}.mkv"} for i in range(105)]
        set_responses(mock_urlopen, torrent_data={"data": {"files": files}})

        sections = provider.details_extended(result)
        items = details_section(sections, "Files (105)").items

        assert len(items) == 101
        assert items[99] == "e99.mkv"
        assert items[-1] == "...and 5 more"

    @pytest.mark.parametrize(
        "torrent_data, media_data, expected, unexpected",
        [
            (
                {"error": True, "message": "Torrent not found."},
                MEDIA_DETAILS,
                ["TVDB"],
                ["AniList", "Files (2)"],
            ),
            (
                TORRENT_DETAILS,
                b"not json",
                ["AniList", "Files (2)"],
                ["TVDB"],
            ),
        ],
    )
    def test_failure(
        self,
        provider,
        result,
        mock_urlopen,
        torrent_data,
        media_data,
        expected,
        unexpected,
    ):
        set_responses(
            mock_urlopen, torrent_data=torrent_data, media_data=media_data
        )

        sections = provider.details_extended(result)
        fields = details_fields(sections)
        # Field labels and section titles
        names = set(fields) | {s.title for s in sections}

        # Details from search are still shown
        assert fields["Uploader"] == "uploader1"
        for name in expected:
            assert name in names
        for name in unexpected:
            assert name not in names

    def test_without_media(self, provider, mock_urlopen):
        set_responses(mock_urlopen, search(torrent(media_id=None)))
        [result] = provider.search("example")
        mock_urlopen.reset_mock()

        provider.details_extended(result)

        urls = [c.args[0] for c in mock_urlopen.call_args_list]
        assert urls == ["https://nekobt.to/api/v1/torrents/1000001"]
