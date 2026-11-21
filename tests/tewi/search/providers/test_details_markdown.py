"""Regression tests for Markdown injection in search result details.

Details are shown in Markdown widget, so text from search providers must
not add headings, list items or links with misleading text.
"""

from unittest.mock import patch

import pytest
from markdown_it import MarkdownIt

from src.tewi.search.models import SearchResult
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


def render(md: str) -> tuple[list[str], list[str]]:
    """Parse Markdown the same way as Textual Markdown widget.

    Returns:
        Tuple of (headings, link targets)
    """
    tokens = MarkdownIt("gfm-like").parse(md)
    headings = [
        tokens[i + 1].content
        for i, t in enumerate(tokens)
        if t.type == "heading_open"
    ]
    links = [
        c.attrs["href"]
        for t in tokens
        if t.children
        for c in t.children
        if c.type == "link_open"
    ]
    return headings, links


def jackett(payload: str, imdb: str) -> str:
    provider = JackettProvider("http://jackett", "key")
    result = provider._parse_result(
        {
            "Title": "Title",
            "InfoHash": HASH,
            "Tracker": "t",
            "Description": payload,
            payload: payload,
            "Imdb": imdb,
            "Poster": "https://img.example/poster.jpg",
        }
    )
    return provider.details_extended(result)


def prowlarr(payload: str, imdb: str) -> str:
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


def tpb(payload: str, imdb: str) -> str:
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


def yts(payload: str, imdb: str) -> str:
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


def nyaa(payload: str, imdb: str) -> str:
    result = SearchResult(
        title="Title",
        info_hash=HASH,
        magnet_link=None,
        torrent_link=None,
        provider="Nyaa",
        provider_id="nyaa",
        provider_short="Nyaa",
        fields={
            "nyaa_category": payload,
            "comments": payload,
            "trusted": payload,
            "remake": payload,
        },
    )
    return NyaaProvider().details_extended(result)


def bitmagnet(payload: str, imdb: str) -> str:
    provider = BitmagnetProvider("http://bitmagnet")
    result = provider._parse_torrent_item(
        {
            "contentType": payload,
            "releaseGroup": payload,
            "videoCodec": payload,
            "languages": [{"name": payload}],
            "torrent": {
                "name": "Title",
                "infoHash": HASH,
                "magnetUri": f"magnet:?xt=urn:btih:{HASH}",
                "tagNames": [payload],
            },
        }
    )
    content = provider._parse_content_details(
        {
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
    )
    with patch.object(provider, "_fetch_content_details", return_value=content):
        return provider.details_extended(result)


DETAILS = [jackett, prowlarr, tpb, yts, nyaa, bitmagnet]


@pytest.mark.parametrize("details", DETAILS)
def test_remote_text_does_not_add_headings_or_links(details):
    md = details(PAYLOAD, LINK_PAYLOAD)
    headings, links = render(md)

    assert "Verified" not in headings
    assert not any("evil" in link for link in links)
    # Payload is still shown, as plain text
    assert "Nice release" in md


@pytest.mark.parametrize(
    "details, imdb, expected",
    [
        (jackett, "111161", "https://www.imdb.com/title/tt111161/"),
        (prowlarr, "111161", "https://www.imdb.com/title/tt111161/"),
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
    _, links = render(details("text", imdb))

    assert expected in links


@pytest.mark.parametrize(
    "details, expected",
    [
        (jackett, "https://img.example/poster.jpg"),
        (prowlarr, "https://img.example/poster.jpg"),
        (bitmagnet, "https://www.themoviedb.org/movie/278"),
    ],
)
def test_safe_urls_from_provider_are_linked(details, expected):
    _, links = render(details("text", "1"))

    assert expected in links
