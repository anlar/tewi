"""Unit tests for nekoBT provider (without nekoBT)."""

import io
import json
import urllib.error
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.nekobt import NekoBtProvider

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
        assert result.categories == [StandardCategories.TV_ANIME]
        assert result.seeders == 46
        assert result.leechers == 2
        assert result.downloads == 803
        assert result.size == 8423228390
        assert result.upload_date.year == 2026
        assert result.fields["torrent_id"] == "1000001"
        assert result.fields["media_id"] == "s1001"

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

    def test_magnet_for_other_torrent_is_rebuilt(self, provider, mock_urlopen):
        other = "magnet:?xt=urn:btih:" + "f" * 40
        set_responses(mock_urlopen, search(torrent(magnet=other)))

        [result] = provider.search("example")

        assert result.magnet_link.startswith(f"magnet:?xt=urn:btih:{HASH}")
        assert "&tr=" not in result.magnet_link

    def test_missing_optional_fields(self, provider, mock_urlopen):
        data = {"id": "1000001", "title": "Example", "infohash": HASH}
        set_responses(mock_urlopen, search(data))

        [result] = provider.search("example")

        assert result.categories is None
        assert result.seeders is None
        assert result.size is None
        assert result.upload_date is None
        assert "media_id" not in result.fields


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
            [StandardCategories.TV_ANIME],
            [StandardCategories.MOVIES],
        ]

    def test_movies(self, provider, mock_urlopen, mixed):
        results = provider.search("example", [StandardCategories.MOVIES])

        assert [r.info_hash for r in results] == ["b" * 40]
        # Movies are rarely among most seeded torrents
        assert request_params(mock_urlopen)["sort_by"] == ["best"]

    def test_tv_subcategory(self, provider, mock_urlopen, mixed):
        results = provider.search("example", [StandardCategories.TV_HD])

        assert [r.info_hash for r in results] == [HASH]
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
        md = provider.details_extended(result)

        assert "- **Audio:** ja, en\n" in md
        assert "- **Subtitles:** en, de\n" in md
        assert "- **Uploader:** uploader1\n" in md
        assert "- **Groups:** Group, \\[x\\]\\(http\\://evil\\)\n" in md
        assert "- **Batch:** Yes\n" in md
        assert "- **AniList:** https://anilist.co/anime/2001\n" in md
        assert "- **TVDB:** https://thetvdb.com/dereferrer/series/3001\n" in md
        assert "- **TMDB:** https://www.themoviedb.org/tv/4001\n" in md
        assert "- **IMDB:** https://www.imdb.com/title/tt0000001/\n" in md
        assert "## Files (2)\n" in md
        assert "- Example/Example \\- 01\\.mkv (1 kB)\n" in md
        assert "- \\# README\n" in md
        # Remote Markdown description and media info aren't shown
        assert "Remote" not in md
        assert "Unique ID" not in md

    def test_anonymous_uploader(self, provider, mock_urlopen):
        set_responses(mock_urlopen, search(torrent(anonymous=True)))
        [result] = provider.search("example")

        md = provider.details_extended(result)

        assert "- **Uploader:** Anonymous\n" in md
        assert "uploader1" not in md

    def test_movie_tmdb_link(self, provider, mock_urlopen):
        set_responses(mock_urlopen, search(torrent(media_id="m1002")))
        [result] = provider.search("example")

        md = provider.details_extended(result)

        assert "- **TMDB:** https://www.themoviedb.org/movie/4001\n" in md

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

        md = provider.details_extended(result)

        assert "## Links" not in md
        assert "anilist.co" not in md
        assert "imdb.com" not in md

    def test_files_are_limited(self, provider, result, mock_urlopen):
        files = [{"path": f"e{i}.mkv"} for i in range(105)]
        set_responses(mock_urlopen, torrent_data={"data": {"files": files}})

        md = provider.details_extended(result)

        assert "## Files (105)\n" in md
        assert "- e99\\.mkv\n" in md
        assert "e100" not in md
        assert "- ...and 5 more\n" in md

    @pytest.mark.parametrize(
        "torrent_data, media_data, expected, unexpected",
        [
            (
                {"error": True, "message": "Torrent not found."},
                MEDIA_DETAILS,
                ["TVDB"],
                ["AniList", "## Files"],
            ),
            (
                TORRENT_DETAILS,
                b"not json",
                ["AniList", "## Files"],
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

        md = provider.details_extended(result)

        # Details from search are still shown
        assert "- **Uploader:** uploader1\n" in md
        for text in expected:
            assert text in md
        for text in unexpected:
            assert text not in md

    def test_without_media(self, provider, mock_urlopen):
        set_responses(mock_urlopen, search(torrent(media_id=None)))
        [result] = provider.search("example")
        mock_urlopen.reset_mock()

        provider.details_extended(result)

        urls = [c.args[0] for c in mock_urlopen.call_args_list]
        assert urls == ["https://nekobt.to/api/v1/torrents/1000001"]
