"""Utility functions for torrent operations."""

import hashlib
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import replace

from .models import ClientError, Torrent


def torrents_test(torrents: list[Torrent], target_count: int) -> list[Torrent]:
    """Get test torrent list (for performance testing).

    Args:
        torrents: List of source torrents to duplicate
        target_count: Target number of test torrents to generate (approximate)

    Returns:
        List of duplicated Torrent objects (~target_count items)

    First copy of each torrent keeps its original hash, so it can still be
    used for client operations. Other copies get unique generated hashes,
    as UI tracks torrents by hash.
    """
    if not torrents:
        return []

    # Calculate multiplier to achieve approximately target_count torrents
    multiplier = max(1, math.ceil(target_count / len(torrents)))

    result = []
    idx = 1

    for i in range(multiplier):
        for t in torrents:
            if i == 0:
                t_hash = t.hash
            else:
                t_hash = hashlib.sha1(f"{t.hash}-{idx}".encode()).hexdigest()

            t_copy = replace(
                t, id=idx, name=t.name + "-" + str(idx), hash=t_hash
            )
            result.append(t_copy)
            idx = idx + 1

    return result


def count_torrents_by_status(torrents: list[Torrent]) -> dict[str, int]:
    """Count torrents by status and calculate sizes.

    This is a helper function for computing torrent statistics.

    Args:
        torrents: List of torrents to count

    Returns:
        Dictionary with keys:
            - count: Total number of torrents
            - down: Number of downloading torrents
            - seed: Number of seeding torrents
            - check: Number of checking torrents
            - stop: Number of stopped torrents
            - complete_size: Total completed bytes
            - total_size: Total size when done in bytes
    """
    count = len(torrents)
    down = 0
    seed = 0
    check = 0
    complete_size = 0
    total_size = 0

    for t in torrents:
        total_size += t.size_when_done
        complete_size += t.size_when_done - t.left_until_done

        if t.status == "downloading":
            down += 1
        elif t.status == "seeding":
            seed += 1
        elif t.status == "checking":
            check += 1

    stop = count - down - seed - check

    return {
        "count": count,
        "down": down,
        "seed": seed,
        "check": check,
        "stop": stop,
        "complete_size": complete_size,
        "total_size": total_size,
    }


# Redirect statuses followed when downloading torrent file
REDIRECT_CODES = (301, 302, 303, 307, 308)

# Max number of redirects followed when downloading torrent file
MAX_REDIRECTS = 5

# Max size of downloaded torrent file (qBittorrent default limit)
MAX_TORRENT_SIZE = 100 * 1024 * 1024  # bytes

DOWNLOAD_TIMEOUT = 30  # seconds


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Don't follow redirects automatically.

    Redirects are followed by `download_torrent_from_url` itself, so
    target scheme is checked on each step and magnet links are detected.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch_torrent(
    opener: urllib.request.OpenerDirector, url: str
) -> tuple[str | None, bytes | None]:
    """Make single request for torrent file without following redirects.

    Returns:
        Tuple of (redirect_url, torrent_data), one of them is non-None

    Raises:
        ClientError: If request fails or response isn't a torrent file
    """
    try:
        with opener.open(url, timeout=DOWNLOAD_TIMEOUT) as response:
            if response.status != 200:
                raise ClientError(
                    f"Failed to download torrent: HTTP {response.status}"
                )
            torrent_data = response.read(MAX_TORRENT_SIZE + 1)
    except urllib.error.HTTPError as e:
        e.close()
        if e.code in REDIRECT_CODES:
            location = e.headers.get("Location")
            if not location:
                raise ClientError(f"Redirect {e.code} missing Location header")
            # Location may be relative to requested URL
            return (urllib.parse.urljoin(url, location.strip()), None)

        raise ClientError(
            f"HTTP error downloading torrent: {e.code} {e.reason}"
        )
    except urllib.error.URLError as e:
        raise ClientError(f"Failed to download torrent from {url}: {e.reason}")
    except ClientError:
        raise
    except Exception as e:
        raise ClientError(f"Error downloading torrent from URL: {str(e)}")

    if len(torrent_data) > MAX_TORRENT_SIZE:
        raise ClientError(
            "Downloaded torrent file is too large "
            f"(over {MAX_TORRENT_SIZE // (1024 * 1024)} MiB)"
        )

    # Validate it's actually a torrent file (bencoded format starts with 'd')
    if not torrent_data or torrent_data[0:1] != b"d":
        raise ClientError("Downloaded content is not a valid torrent file")

    return (None, torrent_data)


def download_torrent_from_url(url: str) -> tuple[str | None, bytes | None]:
    """Download torrent from URL, handling both magnet links and files.

    This utility function handles:
    1. Direct magnet links - returns the magnet link as-is
    2. HTTP/HTTPS URLs that may redirect to either:
       - Magnet links (returns the magnet link)
       - Torrent files (downloads and returns the file data)

    URL may come from search provider, so only magnet and HTTP(S) URLs
    are accepted, including redirect targets (e.g. redirect to file://
    would read local file), and number of redirects and size of
    downloaded file are limited.

    Args:
        url: Magnet link, or HTTP/HTTPS URL to .torrent file

    Returns:
        Tuple of (magnet_link, torrent_data) where:
        - (magnet_link, None) if input is magnet or redirects to magnet
        - (None, torrent_data) if download returns a valid torrent file
        Exactly one of the two values will be non-None.

    Raises:
        ClientError: If download fails, URL is invalid, or downloaded
                    content is neither a valid magnet link nor torrent file
    """
    url = url.strip()
    opener = urllib.request.build_opener(_NoRedirectHandler())

    for _ in range(MAX_REDIRECTS + 1):
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme == "magnet":
            return (url, None)
        if scheme not in ("http", "https"):
            raise ClientError(
                f"Unsupported torrent link scheme: {scheme or '(none)'}"
            )

        redirect_url, torrent_data = _fetch_torrent(opener, url)
        if redirect_url is None:
            return (None, torrent_data)
        url = redirect_url

    raise ClientError(
        f"Failed to download torrent: more than {MAX_REDIRECTS} redirects"
    )
