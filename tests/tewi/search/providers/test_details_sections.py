# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for remote text in search result details.

Details are shown literally, so text from search providers must stay in
values: it must not add sections or links with misleading text. Only
provider-built links and HTTP(S) URLs are shown as links.
"""

from unittest.mock import patch

import pytest

from src.tewi.search.models import DetailsLink, DetailsSection, SearchResult
from src.tewi.search.providers.bitmagnet import BitmagnetProvider
from src.tewi.search.providers.jackett import JackettProvider
from src.tewi.search.providers.nyaa import NyaaProvider
from src.tewi.search.providers.prowlarr import ProwlarrProvider
from src.tewi.search.providers.tpb import TPBProvider
from src.tewi.search.providers.yts import YTSProvider

HASH = "a" * 40

PAYLOAD = (
    "Nice release\n"
    "## Verified\n"
    "- **Scanned:** clean\n"
    "[https://www.imdb.com/title/tt0111161/](https://evil.example/setup.exe)"
)

# Payload for values shown as links (e.g. IMDB ID)
LINK_PAYLOAD = "tt0111161/) [Trailer](https://evil.example/t"


def links(sections: list[DetailsSection]) -> list[str]:
    """URLs of all links in sections."""
    return [
        value.url
        for s in sections
        for _, value in s.fields
        if isinstance(value, DetailsLink)
    ]


def texts(sections: list[DetailsSection]) -> list[str]:
    """All text values in sections: field values, items and paragraphs."""
    result = []
    for s in sections:
        result += [v for _, v in s.fields if isinstance(v, str)]
        result += s.items
        if s.text:
            result.append(s.text)
    return result


def jackett(payload: str, imdb: str) -> list[DetailsSection]:
    provider = JackettProvider("http://jackett", "key")
    result = provider._parse_result(
        {
            "Title": "Title",
            "InfoHash": HASH,
            "Tracker": "t",
            "Description": payload,
            payload: payload,
            "Imdb": imdb,
            # Poster is hidden (Jackett proxy link has API key)
            "Homepage": "https://img.example/poster.jpg",
        }
    )
    return provider.details_extended(result)


def prowlarr(payload: str, imdb: str) -> list[DetailsSection]:
    provider = ProwlarrProvider("http://prowlarr", "key")
    result = provider._parse_result(
        {
            "title": "Title",
            "infoHash": HASH,
            "indexerFlags": [payload],
            "commentUrl": payload,
            payload: payload,
            "imdbId": imdb,
            "posterUrl": "https://img.example/poster.jpg",
        }
    )
    return provider.details_extended(result)


def tpb(payload: str, imdb: str) -> list[DetailsSection]:
    provider = TPBProvider()
    result = provider._parse_torrent(
        {
            "name": "Title",
            "info_hash": HASH,
            "seeders": "1",
            "leechers": "1",
            "size": "1",
            "username": payload,
            "status": payload,
            "imdb": imdb,
        }
    )
    return provider.details_extended(result)


def yts(payload: str, imdb: str) -> list[DetailsSection]:
    provider = YTSProvider()
    result = provider._parse_torrent(
        {
            "title": "Title",
            "year": payload,
            "language": "en",
            "rating": payload,
            "runtime": payload,
            "genres": [payload],
            "summary": payload,
            "imdb_code": imdb,
            "yt_trailer_code": imdb,
        },
        {
            "hash": HASH,
            "quality": payload,
            "video_codec": payload,
            "type": payload,
            "bit_depth": payload,
            "audio_channels": payload,
        },
    )
    return provider.details_extended(result)


def nyaa(payload: str, imdb: str) -> list[DetailsSection]:
    result = SearchResult(
        title="Title",
        info_hash=HASH,
        magnet_link=None,
        torrent_link=None,
        provider="Nyaa",
        provider_id="nyaa",
        provider_short="Nyaa",
        extra={
            "nyaa_category": payload,
            "comments": payload,
            "trusted": payload,
            "remake": payload,
        },
    )
    return NyaaProvider().details_extended(result)


def bitmagnet(payload: str, imdb: str) -> list[DetailsSection]:
    provider = BitmagnetProvider("http://bitmagnet")
    result = provider._parse_torrent_item(
        {
            "infoHash": HASH,
            "contentType": payload,
            "releaseGroup": payload,
            "videoCodec": payload,
            "languages": [{"name": payload}],
            "torrent": {
                "name": "Title",
                "magnetUri": f"magnet:?xt=urn:btih:{HASH}",
                "tagNames": [payload],
            },
        }
    )
    content = {
        "title": payload,
        "overview": payload,
        "releaseDate": payload,
        "originalLanguage": {"name": payload},
        "externalLinks": [
            {"metadataSource": {"name": payload}, "url": payload},
            {"metadataSource": {"name": "IMDb"}, "url": imdb},
            {
                "metadataSource": {"name": "TMDB"},
                "url": "https://www.themoviedb.org/movie/278",
            },
        ],
    }
    details = {"content": content, "files": None}
    with patch.object(provider, "_fetch_details", return_value=details):
        return provider.details_extended(result)


DETAILS = [jackett, prowlarr, tpb, yts, nyaa, bitmagnet]


@pytest.mark.parametrize("details", DETAILS)
def test_remote_text_does_not_add_sections_or_links(details):
    sections = details(PAYLOAD, LINK_PAYLOAD)

    assert "Verified" not in [s.title for s in sections]
    assert not any("evil" in url for url in links(sections))
    # Payload is still shown, as text
    assert any("Nice release" in text for text in texts(sections))


@pytest.mark.parametrize(
    "details, imdb, expected",
    [
        (jackett, "111161", "https://www.imdb.com/title/tt0111161/"),
        (prowlarr, "111161", "https://www.imdb.com/title/tt0111161/"),
        (tpb, "tt0111161", "https://www.imdb.com/title/tt0111161/"),
        (yts, "tt0111161", "https://www.imdb.com/title/tt0111161"),
        (yts, "tt0111161", "https://www.youtube.com/watch?v=tt0111161"),
        (
            bitmagnet,
            "https://www.imdb.com/title/tt0111161",
            "https://www.imdb.com/title/tt0111161",
        ),
    ],
)
def test_valid_links_are_kept(details, imdb, expected):
    assert expected in links(details("text", imdb))


@pytest.mark.parametrize(
    "details, expected",
    [
        (jackett, "https://img.example/poster.jpg"),
        (prowlarr, "https://img.example/poster.jpg"),
        (bitmagnet, "https://www.themoviedb.org/movie/278"),
    ],
)
def test_http_urls_from_provider_are_linked(details, expected):
    assert expected in links(details("text", "1"))


@pytest.mark.parametrize(
    "details, title, field",
    [(yts, "Summary", "Summary"), (bitmagnet, "Overview", "Overview")],
)
def test_long_text_is_paragraph(details, title, field):
    """Long text is shown as paragraph, not squeezed into field value."""
    sections = details("Long text", "1")

    [section] = [s for s in sections if s.title == title]
    assert section.text == "Long text"
    assert all(label != field for s in sections for label, _ in s.fields)
