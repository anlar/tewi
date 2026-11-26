# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utility functions for torrent search operations."""

import html
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.client import HTTPResponse
from typing import Any

from ..util.misc import is_http_url, is_torrent_hash, parse_count
from .models import Category, DetailsLink, StandardCategories

# User-Agent string to imitate a popular browser
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _check_scheme(url: str) -> None:
    """Allow only HTTP(S) URLs (urllib also opens file:// and ftp://).

    Raises:
        urllib.error.URLError: If URL has other scheme
    """
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise urllib.error.URLError(f"unsupported URL scheme: {scheme!r}")


def urlopen(
    url: str, timeout: int = 30, headers: dict[str, str] | None = None
) -> HTTPResponse:
    """Open URL with User-Agent header.

    Creates a Request object with User-Agent header set to imitate
    a popular browser, preventing blocking by search providers.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (default: 30)
        headers: Extra request headers (e.g. API key)

    Returns:
        HTTP response context manager

    Raises:
        urllib.error.URLError: If network request fails or URL isn't HTTP(S)
    """
    _check_scheme(url)
    request = urllib.request.Request(url)  # noqa: S310 (scheme checked)
    request.add_header("User-Agent", USER_AGENT)
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


def urlopen_post(
    url: str,
    data: bytes,
    timeout: int = 30,
    headers: dict[str, str] | None = None,
) -> HTTPResponse:
    """Open URL with POST request and User-Agent header.

    Creates a Request object with User-Agent header set to imitate
    a popular browser, preventing blocking by search providers.
    Sends data as POST request body.

    Args:
        url: URL to fetch
        data: POST data as bytes
        timeout: Request timeout in seconds (default: 30)
        headers: Extra request headers (e.g. API key)

    Returns:
        HTTP response context manager

    Raises:
        urllib.error.URLError: If network request fails or URL isn't HTTP(S)
    """
    _check_scheme(url)
    request = urllib.request.Request(url, data=data)  # noqa: S310
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


# Max size of search provider response (large Jackett or Prowlarr search
# over many indexers is a few MB)
MAX_RESPONSE_SIZE = 20 * 1024 * 1024  # bytes

# Max size of error response body read, it's only used in error message
MAX_ERROR_BODY_SIZE = 4096  # bytes


def read_response(response: Any) -> bytes:
    """Read search provider response, limiting its size.

    Raises:
        urllib.error.URLError: If response is larger than MAX_RESPONSE_SIZE
    """
    data = response.read(MAX_RESPONSE_SIZE + 1)
    if len(data) > MAX_RESPONSE_SIZE:
        raise urllib.error.URLError(
            f"response is larger than {MAX_RESPONSE_SIZE // (1024 * 1024)} MiB"
        )
    return data


def local_time(value: datetime | None) -> datetime | None:
    """Convert search result date to local time zone.

    Providers report dates in different time zones (UTC, site zone, or
    naive local time), so they are converted to be shown consistently.

    Args:
        value: Date, naive one is taken as local time

    Returns:
        Timezone-aware date in local time zone, or None
    """
    return value.astimezone() if value else None


def parse_timestamp(value: object) -> datetime | None:
    """Parse optional date from unix timestamp in provider response.

    Args:
        value: Unix timestamp as int or digit string

    Returns:
        Date in local time zone, or None if value isn't a valid
        timestamp
    """
    timestamp = parse_count(value)
    if not timestamp:
        return None

    try:
        return local_time(datetime.fromtimestamp(timestamp))
    except (OverflowError, OSError, ValueError):
        return None


def details_value(value: object) -> str | DetailsLink:
    """Format remote value for search result details.

    HTTP(S) URLs are shown as links, other values as text.

    Args:
        value: Value to format

    Returns:
        Link for HTTP(S) URL, otherwise value as text
    """
    text = str(value).strip()
    if is_http_url(text):
        return DetailsLink(text)
    return text


# Max size of description shown in search result details
MAX_DESCRIPTION_LINES = 30
MAX_DESCRIPTION_CHARS = 2000

_HTML_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def format_description(value: object, title: object = None) -> str | None:
    """Convert HTML description from provider to plain text.

    Line breaks are kept, consecutive empty lines are merged and long
    descriptions are truncated to MAX_DESCRIPTION_LINES/CHARS.

    Args:
        value: HTML description
        title: Torrent title, description repeating it isn't shown

    Returns:
        Description, or None if it is empty or repeats the title
    """
    if not value or not isinstance(value, str):
        return None

    text = _HTML_BR_RE.sub("\n", value)
    text = html.unescape(_HTML_TAG_RE.sub(" ", text))

    lines: list[str] = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()

    if not lines or " ".join(lines).strip() == html.unescape(str(title)):
        return None

    return "\n".join(_truncate_description(lines))


def _truncate_description(lines: list[str]) -> list[str]:
    """Limit description to MAX_DESCRIPTION_LINES/CHARS.

    Args:
        lines: Description lines

    Returns:
        Lines, ending with ellipsis if description was truncated
    """
    result: list[str] = []
    chars = 0
    for line in lines:
        if len(result) == MAX_DESCRIPTION_LINES:
            break
        if chars + len(line) > MAX_DESCRIPTION_CHARS:
            result.append(line[: MAX_DESCRIPTION_CHARS - chars])
            break
        result.append(line)
        chars += len(line)
    else:
        return result

    result[-1] = result[-1].rstrip() + "…"
    return result


_NON_WORD_RE = re.compile(r"[\W_]+")


def query_words(query: str) -> list[str]:
    """Split search query to lowercase words, ignoring punctuation.

    Args:
        query: Search query

    Returns:
        Query words
    """
    return _NON_WORD_RE.sub(" ", query.casefold()).split()


def matches_query(title: str, words: list[str]) -> bool:
    """Check that torrent title contains all query words.

    Used to remove fuzzy matches returned by some providers (e.g.
    "Exemplar" for "example"). Words are matched as substrings, so release
    names without separators (e.g. "TheShow3") are matched too.

    Args:
        title: Torrent title
        words: Query words from `query_words`

    Returns:
        True if title contains all words
    """
    normalized = " ".join(query_words(title))
    return all(word in normalized for word in words)


def build_magnet_link(
    info_hash: str, name: str, trackers: list[str] | None = None
) -> str:
    """Build a magnet link from info hash, name, and optional trackers.

    Args:
        info_hash: Torrent info hash (40-char hex or 32-char Base32)
        name: Torrent name to encode in magnet link
        trackers: Optional list of tracker URLs to append

    Returns:
        Complete magnet link string

    Raises:
        ValueError: If info hash is not valid (it comes from search
                    provider and could inject extra magnet parameters,
                    e.g. trackers or download sources)
    """
    if not is_torrent_hash(info_hash or ""):
        raise ValueError(f"Invalid info hash: {info_hash!r}")

    encoded_name = urllib.parse.quote(name)
    magnet = f"magnet:?xt=urn:btih:{info_hash.strip()}&dn={encoded_name}"

    if trackers:
        for tracker in trackers:
            encoded_tracker = urllib.parse.quote(tracker, safe="/:")
            magnet += f"&tr={encoded_tracker}"

    return magnet


def detect_category_from_name(name: str) -> Category | None:
    """Detect category from torrent name using pattern matching.

    Args:
        name: Torrent name/title

    Returns:
        Detected Jackett Category or None if no pattern matches
    """
    name_lower = name.lower()

    # TV: contains season and episode as separate token - S01, S01E01
    if re.search(r"(?<![a-z0-9])s\d{2}(?!\d)", name_lower):
        return StandardCategories.TV

    # AUDIO: Check for audio file extensions and keywords
    audio_patterns = [
        ".mp3",
        ".flac",
        ".wav",
        ".aac",
        ".ogg",
        ".m4a",
        ".wma",
        ".alac",
        "album",
        "discography",
        "soundtrack",
        "ost",
        "music",
    ]
    if any(pattern in name_lower for pattern in audio_patterns):
        return StandardCategories.AUDIO

    # VIDEO: Check for video file extensions and keywords
    video_uhd_patterns = [
        "2160p",
        "4k",
    ]
    if any(pattern in name_lower for pattern in video_uhd_patterns):
        return StandardCategories.MOVIES_UHD

    video_hd_patterns = [
        "1080p",
        "720p",
    ]
    if any(pattern in name_lower for pattern in video_hd_patterns):
        return StandardCategories.MOVIES_HD

    video_patterns = [
        ".mkv",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        "movie",
        "film",
        "bluray",
        "webrip",
        "hdtv",
        "x264",
        "x265",
        "hevc",
        "dvdrip",
    ]
    if any(pattern in name_lower for pattern in video_patterns):
        return StandardCategories.MOVIES

    # OTHER: Check for documents, archives, and other content FIRST
    # (before SOFTWARE to avoid "ebook" matching "app" in application)
    other_patterns = [
        ".pdf",
        ".epub",
        ".mobi",
        ".azw",
        ".doc",
        ".txt",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        " book",
        "ebook",
        "magazine",
        "comic",
        "tutorial",
    ]
    if any(pattern in name_lower for pattern in other_patterns):
        return StandardCategories.BOOKS

    # SOFTWARE: Check for software extensions and keywords
    software_patterns = [
        ".exe",
        ".msi",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
        ".app",
        "software",
        "program",
        "application",
        "installer",
        "setup",
        "patch",
        "crack",
        "keygen",
        "portable",
    ]
    if any(pattern in name_lower for pattern in software_patterns):
        return StandardCategories.PC

    # GAMES: Check for game-related keywords
    games_patterns = [
        "game",
        "repack",
        "fitgirl",
        "codex",
        "skidrow",
        "plaza",
        "gog",
        "steam",
        "gameplay",
        "pc game",
        "ps4",
        "ps5",
        "xbox",
        "switch",
        "nintendo",
    ]
    if any(pattern in name_lower for pattern in games_patterns):
        return StandardCategories.CONSOLE

    # XXX: Check for adult content keywords
    xxx_patterns = ["xxx", "adult", "18+", "nsfw", "porn"]
    if any(pattern in name_lower for pattern in xxx_patterns):
        return StandardCategories.XXX

    # No pattern matched
    return None
