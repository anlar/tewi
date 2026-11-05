#!/usr/bin/env python3

"""Download GeoIP country data and convert it to Tewi data file.

Data is "user-country" database from sapics/ip-location-db, published
under PDDL (public domain, no attribution required):
https://github.com/sapics/ip-location-db

Run on release, output file isn't stored in repository. File format is
described in ``src/tewi/util/geoip.py``.
"""

import argparse
import array
import csv
import datetime
import gzip
import hashlib
import io
import struct
import sys
import urllib.request
from pathlib import Path

RELEASE_URL = "https://github.com/sapics/ip-location-db/releases/download"
DATA_URL = RELEASE_URL + "/latest/user-country-ipv{version}-num.csv"
CHECKSUM_URL = (
    RELEASE_URL + "/checksum/user-country-ipv{version}-num.csv.sha256"
)

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


def download(url: str) -> bytes:
    """Download file by HTTPS URL."""
    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are allowed: {url}")
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:  # noqa: S310
        return resp.read()


def download_verified(version: int) -> bytes:
    """Download CSV for IP version and verify its SHA-256 checksum."""
    data = download(DATA_URL.format(version=version))
    expected = download(CHECKSUM_URL.format(version=version)).split()[0]
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected.decode("ascii").lower():
        raise ValueError(f"IPv{version} data checksum mismatch: {actual}")
    return data


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
    content = encode(date, download_verified(4), download_verified(6))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(args.output, "wb", compresslevel=9, mtime=0) as f:
        f.write(content)
    print(f"GeoIP data from {date} written to {args.output}")


if __name__ == "__main__":
    main()
