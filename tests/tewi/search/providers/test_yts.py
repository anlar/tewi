# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for YTS provider (without YTS)."""

import json
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.yts import YTSProvider

TORRENT = {
    "url": "https://yts.pw/torrent/download/AC418DB33FA5CEA4FAB11BC58008FE08F291C9BE",
    "hash": "AC418DB33FA5CEA4FAB11BC58008FE08F291C9BE",
    "quality": "720p",
    "type": "bluray",
    "is_repack": "0",
    "video_codec": "x264",
    "bit_depth": "8",
    "audio_channels": "2.0",
    "seeds": 100,
    "peers": 30,
    "size_bytes": 890199081,
    "date_uploaded_unix": 1446344423,
}

MOVIE = {
    "id": 3709,
    "url": "https://yts.pw/movies/the-shawshank-redemption-1994",
    "imdb_code": "tt0111161",
    "title": "The Shawshank Redemption",
    "slug": "the-shawshank-redemption-1994",
    "year": 1994,
    "rating": 9.3,
    "runtime": 142,
    "genres": ["Action", "Crime", "Drama"],
    "summary": "After a banker is sentenced to life in Shawshank Prison...",
    "yt_trailer_code": "PLl99DlL6b4",
    "language": "en",
    "torrents": [TORRENT],
}

TITLE = "The Shawshank Redemption (1994) [720p] [BluRay] [EN]"


@pytest.fixture
def provider():
    return YTSProvider()


def mock_response(mock, data):
    response = mock.return_value.__enter__.return_value
    response.read.return_value = json.dumps(data).encode()


def api_data(*movies):
    return {"status": "ok", "data": {"movies": list(movies)}}


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        mock_response(mock, api_data(MOVIE))
        yield mock


class TestSearch:
    def test_search_request(self, provider, mock_urlopen):
        results = provider.search(" shawshank ")

        url = urlsplit(mock_urlopen.call_args.args[0])
        assert url.netloc == "movies-api.accel.li"
        assert parse_qs(url.query) == {
            "query_term": ["shawshank"],
            "limit": ["50"],
            "sort_by": ["seeds"],
            "order_by": ["desc"],
        }
        assert len(results) == 1

    @pytest.mark.parametrize("query", ["", "  ", None])
    def test_empty_query(self, provider, mock_urlopen, query):
        assert provider.search(query) == []
        mock_urlopen.assert_not_called()

    @pytest.mark.parametrize(
        "categories",
        [
            [StandardCategories.MOVIES],
            [StandardCategories.MOVIES_HD],
            [StandardCategories.TV, StandardCategories.MOVIES],
        ],
    )
    def test_movie_categories(self, provider, mock_urlopen, categories):
        assert len(provider.search("shawshank", categories)) == 1

    @pytest.mark.parametrize(
        "categories",
        [
            [StandardCategories.AUDIO],
            [StandardCategories.TV, StandardCategories.CONSOLE],
            [StandardCategories.TV_HD],
        ],
    )
    def test_other_categories_skip_search(
        self, provider, mock_urlopen, categories
    ):
        assert provider.search("shawshank", categories) == []
        mock_urlopen.assert_not_called()

    @pytest.mark.parametrize(
        "data",
        [
            {"status": "ok", "data": {"movie_count": 0}},
            {"status": "ok", "data": {"movies": None}},
            {"status": "ok", "data": None},
            api_data({**MOVIE, "torrents": None}),
            api_data({**MOVIE, "torrents": "junk"}),
            api_data({k: v for k, v in MOVIE.items() if k != "torrents"}),
        ],
    )
    def test_no_results(self, provider, mock_urlopen, data):
        mock_response(mock_urlopen, data)

        assert provider.search("shawshank") == []

    def test_api_error(self, provider, mock_urlopen):
        mock_response(
            mock_urlopen, {"status": "error", "status_message": "Bad query"}
        )

        with pytest.raises(Exception, match="API error: Bad query"):
            provider.search("shawshank")

    def test_invalid_json(self, provider, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = b"not json"

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("shawshank")

    @pytest.mark.parametrize(
        "data",
        [
            [MOVIE],
            "junk",
            {"status": "ok", "data": {"movies": {"a": MOVIE}}},
        ],
    )
    def test_invalid_response(self, provider, mock_urlopen, data):
        mock_response(mock_urlopen, data)

        with pytest.raises(Exception, match="Failed to parse API response"):
            provider.search("shawshank")

    def test_invalid_results_are_skipped(self, provider, mock_urlopen):
        movies = [
            "junk",
            None,
            {**MOVIE, "title": None},
            {**MOVIE, "title": " "},
            {**MOVIE, "torrents": ["junk", None, {**TORRENT, "hash": "x"}]},
            {**MOVIE, "torrents": [{**TORRENT, "date_uploaded_unix": "x"}]},
            {**MOVIE, "torrents": [{**TORRENT, "is_repack": "x"}]},
            MOVIE,
        ]
        mock_response(mock_urlopen, api_data(*movies))

        results = provider.search("shawshank")

        assert [r.title for r in results] == [TITLE] * 3
        assert results[0].upload_date is None


class TestParse:
    def test_result(self, provider):
        result = provider._parse_torrent(MOVIE, TORRENT)

        assert result.title == TITLE
        assert result.info_hash == TORRENT["hash"].lower()
        assert result.magnet_link.startswith(
            f"magnet:?xt=urn:btih:{TORRENT['hash'].lower()}&dn=The%20Shawshank"
        )
        assert "&tr=udp://tracker.opentrackr.org:1337/announce" in (
            result.magnet_link
        )
        assert result.torrent_link == TORRENT["url"]
        assert result.categories == (StandardCategories.MOVIES_HD,)
        assert result.seeders == 100
        assert result.leechers == 30
        assert result.size == 890199081
        assert (
            result.upload_date
            == datetime.fromtimestamp(1446344423).astimezone()
        )
        assert result.page_url == MOVIE["url"]

    def test_torrents_of_same_quality_differ_by_type(self, provider):
        web = provider._parse_torrent(MOVIE, {**TORRENT, "type": "web"})

        assert web.title == "The Shawshank Redemption (1994) [720p] [WEB] [EN]"

    def test_minimal_result(self, provider):
        result = provider._parse_torrent(
            {"title": "Movie"}, {"hash": TORRENT["hash"]}
        )

        assert result.title == "Movie"
        assert result.categories == (StandardCategories.MOVIES,)
        assert result.page_url is None
        assert result.upload_date is None
        assert result.extra == {}

    @pytest.mark.parametrize(
        "quality, category",
        [
            ("480p", StandardCategories.MOVIES_SD),
            ("720p", StandardCategories.MOVIES_HD),
            ("1080p", StandardCategories.MOVIES_HD),
            ("1080p.x265", StandardCategories.MOVIES_HD),
            ("2160p", StandardCategories.MOVIES_UHD),
            ("3D", StandardCategories.MOVIES_3D),
            ("8K", StandardCategories.MOVIES),
            (None, StandardCategories.MOVIES),
        ],
    )
    def test_category(self, provider, quality, category):
        result = provider._parse_torrent(MOVIE, {**TORRENT, "quality": quality})

        assert result.categories == (category,)

    @pytest.mark.parametrize(
        "movie, expected",
        [
            (
                {"url": "https://yts.pw/movies/m?ref=1"},
                "https://yts.pw/movies/m",
            ),
            ({"slug": "m-2000"}, "https://yts.pw/movies/m-2000"),
            ({"id": 1}, None),
        ],
    )
    def test_page_url(self, provider, movie, expected):
        result = provider._parse_torrent({"title": "M", **movie}, TORRENT)

        assert result.page_url == expected


class TestDetails:
    def test_sections(self, provider):
        result = provider._parse_torrent(MOVIE, {**TORRENT, "is_repack": "1"})

        sections = provider.details_extended(result)

        assert [s.title for s in sections] == ["Movie", "Summary", "Quality"]
        movie, summary, quality = sections
        assert [label for label, _ in movie.fields] == [
            "Year",
            "Runtime",
            "Genres",
            "Language",
            "Rating",
            "IMDB",
            "Trailer",
        ]
        assert dict(movie.fields)["Runtime"] == "142 min"
        assert dict(movie.fields)["Genres"] == "Action, Crime, Drama"
        assert dict(movie.fields)["Rating"] == "9.3/10"
        assert summary.text == MOVIE["summary"]
        assert dict(quality.fields) == {
            "Type": "bluray",
            "Quality": "720p",
            "Video Codec": "x264",
            "Bit Depth": "8",
            "Audio Channels": "2.0",
            "Repack": "Yes",
        }

    @pytest.mark.parametrize("is_repack", ["0", "", None])
    def test_not_repack(self, provider, is_repack):
        result = provider._parse_torrent(
            MOVIE, {**TORRENT, "is_repack": is_repack}
        )

        assert "is_repack" not in result.extra
