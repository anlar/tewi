"""Utility functions for torrent operations."""

import math
import urllib.error
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
    """
    if not torrents:
        return []

    # Calculate multiplier to achieve approximately target_count torrents
    multiplier = max(1, math.ceil(target_count / len(torrents)))

    result = []
    idx = 1

    for i in range(multiplier):
        for t in torrents:
            t_copy = replace(t, id=idx, name=t.name + "-" + str(idx))
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


def _handle_redirect(
    error: urllib.error.HTTPError,
) -> tuple[str | None, bytes | None]:
    """Handle HTTP redirect responses, checking for magnet links.

    Args:
        error: HTTPError containing redirect information

    Returns:
        Tuple of (magnet_link, torrent_data) from following redirect

    Raises:
        ClientError: If redirect location is missing or download fails
    """
    location = error.headers.get("Location")
    if not location:
        raise ClientError(f"Redirect {error.code} missing Location header")

    # Check if redirect is to a magnet link
    if location.startswith("magnet:"):
        return (location, None)

    # Otherwise, follow the redirect by calling recursively
    return download_torrent_from_url(location)


def download_torrent_from_url(url: str) -> tuple[str | None, bytes | None]:
    """Download torrent from URL, handling both magnet links and files.

    This utility function handles:
    1. Direct magnet links - returns the magnet link as-is
    2. HTTP/HTTPS URLs that may redirect to either:
       - Magnet links (returns the magnet link)
       - Torrent files (downloads and returns the file data)

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
    # Handle direct magnet links
    if url.startswith("magnet:"):
        return (url, None)

    # Create custom opener that doesn't automatically follow redirects
    # This allows us to check if redirect target is a magnet link
    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            # Don't follow redirects automatically
            return None

    opener = urllib.request.build_opener(NoRedirectHandler())

    try:
        # Make request without following redirects
        response = opener.open(url, timeout=30)

        # If we got here, no redirect occurred - download the content
        if response.status != 200:
            raise ClientError(
                f"Failed to download torrent: HTTP {response.status}"
            )

        torrent_data = response.read()
        response.close()

        # Validate it's actually a torrent file
        # (bencoded format starts with 'd')
        if not torrent_data or torrent_data[0:1] != b"d":
            raise ClientError("Downloaded content is not a valid torrent file")

        return (None, torrent_data)

    except urllib.error.HTTPError as e:
        # Check if this is a redirect (3xx status codes)
        if e.code in (301, 302, 303, 307, 308):
            return _handle_redirect(e)

        raise ClientError(
            f"HTTP error downloading torrent: {e.code} {e.reason}"
        )
    except urllib.error.URLError as e:
        raise ClientError(f"Failed to download torrent from {url}: {e.reason}")
    except ClientError:
        # Re-raise ClientError as-is
        raise
    except Exception as e:
        raise ClientError(f"Error downloading torrent from URL: {str(e)}")
