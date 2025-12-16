"""Utility functions for torrent search operations."""

import urllib.parse
import urllib.request
from typing import Any

from .models import Category, StandardCategories

# User-Agent string to imitate a popular browser
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def urlopen(url: str, timeout: int = 30) -> Any:
    """Open URL with User-Agent header.

    Creates a Request object with User-Agent header set to imitate
    a popular browser, preventing blocking by search providers.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (default: 30)

    Returns:
        HTTP response context manager

    Raises:
        urllib.error.URLError: If network request fails
    """
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    return urllib.request.urlopen(request, timeout=timeout)


def urlopen_post(url: str, data: bytes, timeout: int = 30) -> Any:
    """Open URL with POST request and User-Agent header.

    Creates a Request object with User-Agent header set to imitate
    a popular browser, preventing blocking by search providers.
    Sends data as POST request body.

    Args:
        url: URL to fetch
        data: POST data as bytes
        timeout: Request timeout in seconds (default: 30)

    Returns:
        HTTP response context manager

    Raises:
        urllib.error.URLError: If network request fails
    """
    request = urllib.request.Request(url, data=data)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Content-Type", "application/json")
    return urllib.request.urlopen(request, timeout=timeout)


def build_magnet_link(
    info_hash: str, name: str, trackers: list[str] | None = None
) -> str:
    """Build a magnet link from info hash, name, and optional trackers.

    Args:
        info_hash: 40-character hex string torrent info hash
        name: Torrent name to encode in magnet link
        trackers: Optional list of tracker URLs to append

    Returns:
        Complete magnet link string
    """
    encoded_name = urllib.parse.quote(name)
    magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={encoded_name}"

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
        "1080p",
        "720p",
        "2160p",
        "4k",
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
