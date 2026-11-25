# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for LimeTorrents provider (without LimeTorrents)."""

from unittest.mock import patch

import pytest

from src.tewi.search.models import DetailsSection, StandardCategories
from src.tewi.search.providers.limetorrents import LimeTorrentsProvider

HASH = "0123456789ABCDEF0123456789ABCDEF01234567"


def item(
    title: str = "Example Show S01 1080p",
    category: str = "TV shows",
    info_hash: str = HASH,
    description: str = "Seeds: 12 , Leechers 4",
    size: str = "11212668",
) -> str:
    return f"""<item><title>{title}</title>
<pubDate>02 Nov 2026 07:30:12 +0200</pubDate>
<link>https://www.limetorrents.fun/Example-Show-torrent-1000001.html</link>
<category>{category}</category><size>{size}</size>
<description>{description}</description>
<enclosure url="https://itorrents.net/torrent/{info_hash}.torrent?title=x"
  type="application/x-bittorrent" /></item>"""


def feed(*items: str) -> bytes:
    return (
        "<?xml version='1.0' encoding='UTF-8' ?>\n"
        f'<rss version="2.0"><channel>{"".join(items)}</channel></rss>\n'
        "<script>(function(){var a=1<2;})();</script>"
    ).encode()


@pytest.fixture
def provider():
    return LimeTorrentsProvider()


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        response = mock.return_value.__enter__.return_value
        response.read.return_value = feed(item())
        yield mock


def set_feed(mock, data: bytes) -> None:
    mock.return_value.__enter__.return_value.read.return_value = data


class TestSearch:
    def test_empty_query(self, provider, mock_urlopen):
        assert provider.search("  ") == []
        mock_urlopen.assert_not_called()

    def test_request(self, provider, mock_urlopen):
        provider.search(" foo/bar: baz ")

        assert mock_urlopen.call_args.args[0] == (
            "https://www.limetorrents.fun/searchrss/foo%2Fbar%3A%20baz/"
        )

    def test_result(self, provider, mock_urlopen):
        [result] = provider.search("example")

        assert result.title == "Example Show S01 1080p"
        assert result.info_hash == HASH.lower()
        assert result.magnet_link.startswith(
            f"magnet:?xt=urn:btih:{HASH.lower()}"
        )
        assert result.torrent_link is None
        assert result.page_url == (
            "https://www.limetorrents.fun/Example-Show-torrent-1000001.html"
        )
        assert result.categories == (StandardCategories.TV,)
        assert result.seeders == 12
        assert result.leechers == 4
        assert result.size == 11212668
        assert result.upload_date.year == 2026

    @pytest.mark.parametrize(
        "link, expected",
        [
            (
                "https://www.limetorrents.fun/Example-Band--Some-Album   "
                "-(2020)-[Flac-24-   -torrent-1000002.html",
                "https://www.limetorrents.fun/Example-Band--Some-Album%20%20%20"
                "-(2020)-%5BFlac-24-%20%20%20-torrent-1000002.html",
            ),
            (
                "https://www.limetorrents.fun/Example-–-⭐-torrent-1000003.html",
                "https://www.limetorrents.fun/Example-%E2%80%93-%E2%AD%90"
                "-torrent-1000003.html",
            ),
            (
                "https://www.limetorrents.fun/Done%20Already-torrent-1000004.html",
                "https://www.limetorrents.fun/Done%20Already-torrent-1000004.html",
            ),
            ("javascript:alert(1)", None),
            ("", None),
        ],
    )
    def test_page_url_is_encoded(self, provider, link, expected):
        assert provider._page_url(link) == expected

    def test_script_after_feed_is_ignored(self, provider, mock_urlopen):
        assert len(provider.search("example")) == 1

    def test_invalid_feed(self, provider, mock_urlopen):
        set_feed(mock_urlopen, b"<html>error</html>")

        with pytest.raises(Exception, match="Failed to parse RSS feed"):
            provider.search("example")

    def test_fuzzy_matches_are_removed(self, provider, mock_urlopen):
        set_feed(
            mock_urlopen,
            feed(item(), item("Exemplar S01", info_hash="B" * 40)),
        )

        assert [r.info_hash for r in provider.search("example")] == [
            HASH.lower()
        ]

    def test_title_is_unescaped(self, provider, mock_urlopen):
        set_feed(mock_urlopen, feed(item("Example Guide --&amp;gt; [x]")))

        [result] = provider.search("example")

        assert result.title == "Example Guide --> [x]"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"info_hash": "x"},
            {"title": ""},
        ],
    )
    def test_invalid_item_is_skipped(self, provider, mock_urlopen, kwargs):
        set_feed(mock_urlopen, feed(item(**kwargs)))

        assert provider.search("example") == []

    def test_missing_peers_and_size(self, provider, mock_urlopen):
        set_feed(mock_urlopen, feed(item(description="", size="")))

        [result] = provider.search("example")

        assert result.seeders is None
        assert result.leechers is None
        assert result.size is None


class TestCategories:
    @pytest.mark.parametrize(
        "category, expected",
        [
            ("Movies", StandardCategories.MOVIES),
            ("TV shows", StandardCategories.TV),
            ("TV shows - Classics", StandardCategories.TV),
            ("Anime.", StandardCategories.TV_ANIME),
            ("Games - Other", StandardCategories.PC_GAMES),
            ("Games - Wii", StandardCategories.CONSOLE_WII),
            ("Applications - Windows", StandardCategories.PC),
            ("Music - Music", StandardCategories.AUDIO),
            ("Other - E-books", StandardCategories.BOOKS_EBOOK),
            ("E-books", StandardCategories.BOOKS_EBOOK),
            ("Other - Other", StandardCategories.OTHER),
            ("Unknown", None),
            (None, None),
        ],
    )
    def test_mapping(self, provider, category, expected):
        assert provider.get_category(category) == expected

    def test_filter(self, provider, mock_urlopen):
        set_feed(
            mock_urlopen,
            feed(
                item(),
                item("Example Anime", "Anime.", "C" * 40),
                item("Example Game", "Games - PC", "D" * 40),
                item("Example Unknown", "Unknown", "E" * 40),
            ),
        )

        results = provider.search("example", [StandardCategories.TV_HD])

        # Subcategory selects whole parent category
        assert [r.info_hash for r in results] == [HASH.lower(), "c" * 40]

    def test_no_filter(self, provider, mock_urlopen):
        set_feed(
            mock_urlopen,
            feed(item(), item("Example Unknown", "Unknown", "E" * 40)),
        )

        assert len(provider.search("example")) == 2


class TestDetails:
    def test_details(self, provider, mock_urlopen):
        set_feed(mock_urlopen, feed(item(category="Other - E-books")))
        [result] = provider.search("example")

        sections = provider.details_extended(result)

        assert sections == [
            DetailsSection(
                "Information", fields=(("Category", "Other - E-books"),)
            )
        ]
