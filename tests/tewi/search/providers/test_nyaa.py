# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for Nyaa provider (without Nyaa)."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.tewi.search.models import StandardCategories
from src.tewi.search.providers.nyaa import NyaaProvider

ITEM = """<item>
<title>[Group] Example Show - 01 [1080p]</title>
<link>https://nyaa.si/download/2160092.torrent</link>
<guid isPermaLink="true">https://nyaa.si/view/2160092</guid>
<pubDate>Sat, 12 Sep 2026 15:45:00 -0000</pubDate>
<nyaa:seeders>48</nyaa:seeders>
<nyaa:leechers>4</nyaa:leechers>
<nyaa:downloads>1742</nyaa:downloads>
<nyaa:infoHash>EF3E7AD1B12BDD9FC341691D8866CD1FA8374A4B</nyaa:infoHash>
<nyaa:categoryId>1_2</nyaa:categoryId>
<nyaa:category>Anime - English-translated</nyaa:category>
<nyaa:size>6.6 GiB</nyaa:size>
<nyaa:comments>3</nyaa:comments>
<nyaa:trusted>Yes</nyaa:trusted>
<nyaa:remake>No</nyaa:remake>
</item>"""


def rss(*items: str) -> bytes:
    return (
        '<rss xmlns:nyaa="https://nyaa.si/xmlns/nyaa" version="2.0">'
        f"<channel><title>Nyaa</title>{''.join(items)}</channel></rss>"
    ).encode()


def item(**replace: str | None) -> str:
    """Build RSS item with replaced tag texts, or removed tags for None
    (keys are tag names with ``nyaa_`` prefix for Nyaa namespace)."""
    result = ITEM
    for key, value in replace.items():
        tag = key.replace("nyaa_", "nyaa:")
        start = result.index(f"<{tag}")
        end = result.index(f"</{tag}>") + len(f"</{tag}>")
        new = f"<{tag}>{value}</{tag}>" if value is not None else ""
        result = result[:start] + new + result[end:]
    return result


@pytest.fixture
def provider():
    return NyaaProvider()


@pytest.fixture
def mock_urlopen():
    with patch("src.tewi.search.base._urlopen") as mock:
        response = mock.return_value.__enter__.return_value
        response.read.return_value = rss()
        yield mock


class TestSearch:
    @pytest.mark.parametrize(
        "categories, expected",
        [
            ([StandardCategories.AUDIO], "2_0"),
            ([StandardCategories.AUDIO_LOSSLESS], "2_0"),
            ([StandardCategories.BOOKS], "3_0"),
            ([StandardCategories.PC], "6_0"),
            ([StandardCategories.OTHER], "5_0"),
            # TV has both Anime and Live Action groups
            ([StandardCategories.TV], "0_0"),
            # Nyaa searches only by one category
            ([StandardCategories.AUDIO, StandardCategories.BOOKS], "0_0"),
            # Categories without Nyaa groups don't change search
            ([StandardCategories.AUDIO, StandardCategories.CONSOLE], "2_0"),
            # Nyaa has no such categories
            ([StandardCategories.CONSOLE], None),
            ([StandardCategories.MOVIES, StandardCategories.XXX], None),
        ],
    )
    def test_convert(self, provider, categories, expected):
        assert provider._convert_categories_to_nyaa(categories) == expected

    def test_search_request(self, provider, mock_urlopen):
        provider.search(" example ")

        url = mock_urlopen.call_args.args[0]
        assert url == "https://nyaa.si/?page=rss&q=example&c=0_0"

    def test_search_request_category(self, provider, mock_urlopen):
        provider.search("example", [StandardCategories.BOOKS])

        url = mock_urlopen.call_args.args[0]
        assert url == "https://nyaa.si/?page=rss&q=example&c=3_0"

    def test_search_request_all_categories(self, provider, mock_urlopen):
        provider.search(
            "example", [StandardCategories.AUDIO, StandardCategories.BOOKS]
        )

        url = mock_urlopen.call_args.args[0]
        assert url == "https://nyaa.si/?page=rss&q=example&c=0_0"

    def test_search_without_nyaa_categories(self, provider, mock_urlopen):
        results = provider.search("example", [StandardCategories.MOVIES])

        assert results == []
        mock_urlopen.assert_not_called()

    @pytest.mark.parametrize(
        "data", [b"not xml", rss().replace(b"Nyaa", b"\xff\xfe")]
    )
    def test_invalid_response(self, provider, mock_urlopen, data):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = data

        with pytest.raises(Exception, match="Failed to parse RSS feed"):
            provider.search("example")

    def test_invalid_items_are_skipped(self, provider, mock_urlopen, caplog):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = rss(
            item(title=""),
            item(nyaa_infoHash="junk"),
            item(pubDate="not a date"),
            ITEM,
        )

        results = provider.search("example")

        assert [r.page_url for r in results] == ["https://nyaa.si/view/2160092"]
        assert "skipping invalid search result '2160092'" in caplog.text


def parse(provider, text: str):
    return provider._parse_item(ET.fromstring(rss(text)).find(".//item"))


class TestParseItem:
    def test_parse_item(self, provider):
        result = parse(provider, ITEM)

        assert result.title == "[Group] Example Show - 01 [1080p]"
        assert result.info_hash == "ef3e7ad1b12bdd9fc341691d8866cd1fa8374a4b"
        assert result.magnet_link.startswith(
            "magnet:?xt=urn:btih:ef3e7ad1b12bdd9fc341691d8866cd1fa8374a4b&dn="
        )
        assert "&tr=http://nyaa.tracker.wf:7777/announce&" in (
            result.magnet_link
        )
        assert result.torrent_link == (
            "https://nyaa.si/download/2160092.torrent"
        )
        assert result.page_url == "https://nyaa.si/view/2160092"
        assert result.categories == (StandardCategories.TV_ANIME,)
        assert result.seeders == 48
        assert result.leechers == 4
        assert result.downloads == 1742
        assert result.size == int(6.6 * 1024**3)
        assert result.upload_date == datetime(
            2026, 9, 12, 15, 45, tzinfo=timezone.utc
        )
        assert result.extra == {
            "comments": "3",
            "trusted": "Yes",
            "remake": "No",
            "nyaa_category": "Anime - English-translated",
        }

    def test_missing_optional_fields(self, provider):
        text = item(
            link=None,
            guid=None,
            pubDate=None,
            nyaa_seeders=None,
            nyaa_size=None,
            nyaa_categoryId=None,
            nyaa_comments=None,
        )

        result = parse(provider, text)

        assert result.torrent_link is None
        assert result.page_url is None
        assert result.upload_date is None
        assert result.seeders is None
        assert result.size is None
        assert result.categories == ()
        assert "comments" not in result.extra

    @pytest.mark.parametrize(
        "code, expected",
        [
            ("2_1", (StandardCategories.AUDIO_LOSSLESS,)),
            ("4_4", (StandardCategories.TV,)),
            ("6_2", (StandardCategories.PC_GAMES,)),
            ("9_9", ()),
        ],
    )
    def test_category(self, provider, code, expected):
        result = parse(provider, item(nyaa_categoryId=code))

        assert result.categories == expected

    @pytest.mark.parametrize(
        "pub_date, expected",
        [
            # Real offset isn't replaced by UTC ("-0000" is in ITEM)
            (
                "Sat, 12 Sep 2026 15:45:00 +0900",
                datetime(2026, 9, 12, 6, 45, tzinfo=timezone.utc),
            ),
        ],
    )
    def test_upload_date(self, provider, pub_date, expected):
        result = parse(provider, item(pubDate=pub_date))

        assert result.upload_date == expected

    @pytest.mark.parametrize("seeders", ["-1", "many", ""])
    def test_invalid_count_is_none(self, provider, seeders):
        result = parse(provider, item(nyaa_seeders=seeders))

        assert result.seeders is None


class TestParseSize:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("1 Byte", 1),
            ("512 Bytes", 512),
            ("1.0 KiB", 1024),
            ("446.1 MiB", int(446.1 * 1024**2)),
            ("21.6 GiB", int(21.6 * 1024**3)),
            ("1.5 TiB", int(1.5 * 1024**4)),
            ("1.2 PiB", int(1.2 * 1024**5)),
            (None, None),
            ("", None),
            ("1.4 GB", None),
            ("1.4 GiBs", None),
            ("GiB", None),
            ("1.4", None),
        ],
    )
    def test_parse_size(self, provider, value, expected):
        assert provider._parse_size(value) == expected
