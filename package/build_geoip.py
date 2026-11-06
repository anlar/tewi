#!/usr/bin/env python3

"""Download GeoIP country data and convert it to Tewi data file.

Data is "user-country" database from sapics/ip-location-db, published
under PDDL (public domain, no attribution required):
https://github.com/sapics/ip-location-db

Run on release, output file isn't stored in repository. File format is
described in ``src/tewi/util/geoip.py``.

Set ``GITHUB_PUBLIC_TOKEN``, ``GITHUB_TOKEN`` or ``GH_TOKEN`` environment
variable (first non-empty is used) to make authenticated GitHub API requests
with higher rate limit.
"""

import argparse
import array
import csv
import datetime
import gzip
import hashlib
import io
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Assets are downloaded with GitHub API: direct release download links
# sometimes fail with 504 Gateway Time-out for hours, while API works
API_HOST = "api.github.com"
RELEASE_API_URL = (
    "https://api.github.com/repos/sapics/ip-location-db/releases/tags/latest"
)
ASSET_NAME = "user-country-ipv{version}-num.csv"

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "tewi"
    / "util"
    / "geoip.dat.gz"
)

MAGIC = b"TEWIGEO\x01"
HEADER = struct.Struct("<8s10sHII")

NO_COUNTRY = "--"
TIMEOUT = 60
ATTEMPTS = 3
RETRY_DELAY = 10
USER_AGENT = "tewi-build-geoip"
TOKEN_VARIABLES = ("GITHUB_PUBLIC_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")


def _is_transient(error: Exception) -> bool:
    """Check if request error is temporary and request may be retried."""
    if isinstance(error, urllib.error.HTTPError):
        return error.code >= 500 or error.code == 429
    return isinstance(error, (urllib.error.URLError, TimeoutError))


def _github_token() -> str | None:
    """Get optional token to raise GitHub API rate limit from environment."""
    for variable in TOKEN_VARIABLES:
        token = os.environ.get(variable)
        if token:
            return token
    return None


def download(url: str, accept: str) -> bytes:
    """Download HTTPS URL, retry on temporary errors."""
    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are allowed: {url}")

    request = urllib.request.Request(  # noqa: S310 (HTTPS checked above)
        url, headers={"Accept": accept, "User-Agent": USER_AGENT}
    )
    token = _github_token()
    if token and urllib.parse.urlsplit(url).hostname == API_HOST:
        # Unredirected: assets redirect to storage host, it must not get token
        request.add_unredirected_header("Authorization", f"Bearer {token}")

    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=TIMEOUT
            ) as resp:
                return resp.read()
        except Exception as e:
            if attempt == ATTEMPTS or not _is_transient(e):
                raise
            delay = RETRY_DELAY * attempt
            print(
                f"Download of {url} failed ({e}), retry in {delay} s",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def download_assets() -> tuple[bytes, bytes]:
    """Download IPv4 and IPv6 CSV, verify their SHA-256 checksums."""
    release = json.loads(download(RELEASE_API_URL, "application/json"))
    assets = {a["name"]: a for a in release["assets"]}

    result = []
    for version in (4, 6):
        name = ASSET_NAME.format(version=version)
        asset = assets.get(name)
        if asset is None:
            raise ValueError(f"Release has no {name} asset")

        algorithm, _, expected = (asset.get("digest") or "").partition(":")
        if algorithm != "sha256":
            raise ValueError(f"Release has no SHA-256 digest for {name}")

        data = download(asset["url"], "application/octet-stream")
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected.lower():
            raise ValueError(f"{name} checksum mismatch: {actual}")
        result.append(data)

    return result[0], result[1]


def build_ranges(
    rows, shift: int, codes: dict[str, int]
) -> tuple[list[int], list[int]]:
    """Convert sorted (first, last, country) rows to range starts.

    Gaps between rows get "no country" index 0, adjacent ranges of the same
    country are merged. Range bounds are shifted right by ``shift`` bits
    (IPv6 is stored by upper 64 bits): range smaller than that covers its
    whole block, later ranges replace earlier ones in the same block.
    """
    starts: list[int] = []
    indexes: list[int] = []

    def append(start: int, index: int) -> None:
        if starts and starts[-1] == start:
            starts.pop()
            indexes.pop()
        if indexes and indexes[-1] == index:
            return
        starts.append(start)
        indexes.append(index)

    def gap_start(prev_last: int) -> int:
        # Round up to the next block, so gap doesn't replace previous range
        return -(-(prev_last + 1) >> shift)

    prev_last = -1
    for first, last, country in rows:
        first, last = int(first), int(last)
        if first <= prev_last or last < first:
            raise ValueError(f"Ranges are not sorted or overlap at {first}")
        valid = len(country) == 2 and country.isascii() and country.isalpha()
        if not valid or not country.isupper():
            raise ValueError(f"Invalid country code: {country!r}")

        if first > prev_last + 1:
            append(gap_start(prev_last), 0)
        append(first >> shift, codes.setdefault(country, len(codes)))
        prev_last = last

    append(gap_start(prev_last), 0)
    return starts, indexes


def encode(date: str, v4_csv: bytes, v6_csv: bytes) -> bytes:
    """Build uncompressed data file content from CSV files."""
    codes = {NO_COUNTRY: 0}
    ranges = []
    for content, shift, max_value in (
        (v4_csv, 0, 2**32),
        (v6_csv, 64, 2**64),
    ):
        rows = csv.reader(io.StringIO(content.decode("ascii")))
        starts, indexes = build_ranges(rows, shift, codes)
        # Range after the last address has no country and is out of bounds
        if starts[-1] >= max_value:
            starts.pop()
            indexes.pop()
        ranges.append((starts, indexes))

    if len(codes) > 256:
        raise ValueError(f"Too many country codes: {len(codes)}")

    (v4_starts, v4_idx), (v6_starts, v6_idx) = ranges
    parts = [
        HEADER.pack(
            MAGIC,
            date.encode("ascii"),
            len(codes),
            len(v4_starts),
            len(v6_starts),
        ),
        "".join(codes).encode("ascii"),
    ]
    for typecode, values in (
        ("I", v4_starts),
        ("B", v4_idx),
        ("Q", v6_starts),
        ("B", v6_idx),
    ):
        arr = array.array(typecode, values)
        if sys.byteorder == "big":
            arr.byteswap()
        parts.append(arr.tobytes())
    return b"".join(parts)


def main() -> None:
    """Download data and write data file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output file (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    try:
        content = encode(date, *download_assets())
    except (OSError, ValueError, KeyError) as e:
        sys.exit(f"Can't build GeoIP data: {e}")

    # Write to temporary file first, so interrupted run doesn't leave
    # partial file, which make would consider up to date
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_name(args.output.name + ".tmp")
    try:
        with gzip.GzipFile(tmp, "wb", compresslevel=9, mtime=0) as f:
            f.write(content)
        tmp.replace(args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"GeoIP data from {date} written to {args.output}")


if __name__ == "__main__":
    main()
