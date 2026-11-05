"""Offline peer country lookup by IP address.

Uses data file generated with ``package/build_geoip.py`` on release (it isn't
stored in repository). File is gzip-compressed, all numbers are
little-endian:

- header: magic, data date (YYYY-MM-DD), code count, IPv4 and IPv6 range
  counts
- country codes: 2 ASCII bytes each, index 0 means "no country"
- IPv4 range starts (uint32) and their country code indexes (uint8)
- IPv6 range starts (upper 64 bits, uint64) and code indexes (uint8)

Each range lasts until start of the next one.
"""

import array
import bisect
import gzip
import ipaddress
import struct
import sys
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

from .countries import get_country_name
from .log import get_logger, log_time

logger = get_logger()

GEOIP_CACHE_SIZE = 5000

DATA_FILE = Path(__file__).with_name("geoip.dat.gz")

MAGIC = b"TEWIGEO\x01"
HEADER = struct.Struct("<8s10sHII")


@dataclass(frozen=True)
class GeoIPData:
    """Loaded IP ranges with their country codes."""

    date: str
    codes: list[str]
    v4_starts: array.array
    v4_codes: array.array
    v6_starts: array.array
    v6_codes: array.array


def _read_array(raw: bytes, offset: int, typecode: str, count: int):
    """Read little-endian array from bytes, return it with next offset."""
    arr = array.array(typecode)
    end = offset + arr.itemsize * count
    if end > len(raw):
        raise ValueError("data file is truncated")
    arr.frombytes(raw[offset:end])
    if sys.byteorder == "big":
        arr.byteswap()
    return arr, end


def parse_data(raw: bytes) -> GeoIPData:
    """Parse uncompressed data file content."""
    if len(raw) < HEADER.size:
        raise ValueError("data file is truncated")

    magic, date, n_codes, n_v4, n_v6 = HEADER.unpack_from(raw)
    if magic != MAGIC:
        raise ValueError("unsupported data file format")

    offset = HEADER.size
    codes_raw = raw[offset : offset + 2 * n_codes]
    codes = [
        codes_raw[i : i + 2].decode("ascii") for i in range(0, 2 * n_codes, 2)
    ]
    offset += 2 * n_codes

    v4_starts, offset = _read_array(raw, offset, "I", n_v4)
    v4_codes, offset = _read_array(raw, offset, "B", n_v4)
    v6_starts, offset = _read_array(raw, offset, "Q", n_v6)
    v6_codes, offset = _read_array(raw, offset, "B", n_v6)

    if offset != len(raw):
        raise ValueError("data file has unexpected trailing bytes")
    if (
        max(v4_codes, default=0) >= n_codes
        or max(v6_codes, default=0) >= n_codes
    ):
        raise ValueError("data file has invalid country index")

    return GeoIPData(
        date=date.decode("ascii"),
        codes=codes,
        v4_starts=v4_starts,
        v4_codes=v4_codes,
        v6_starts=v6_starts,
        v6_codes=v6_codes,
    )


@cache
def _load() -> GeoIPData | None:
    """Load data file on first lookup, None if it's not available."""
    try:
        with gzip.open(DATA_FILE, "rb") as f:
            data = parse_data(f.read())
    except FileNotFoundError:
        logger.warning(
            "GeoIP data file not found, country detection for peers "
            "will not work, unless provided by torrent client itself"
        )
        return None
    except Exception as e:
        logger.warning(
            f"GeoIP data file can't be loaded, country detection for peers "
            f"will not work, unless provided by torrent client itself: {e}"
        )
        return None

    logger.info(
        f"Loaded GeoIP data from {data.date}: {len(data.v4_starts)} IPv4 "
        f"and {len(data.v6_starts)} IPv6 ranges"
    )
    return data


def lookup_code(data: GeoIPData, address: str) -> str | None:
    """Return country code for IP address, None if it's unknown."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None

    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    if ip.version == 4:
        starts, codes, key = data.v4_starts, data.v4_codes, int(ip)
    else:
        starts, codes, key = data.v6_starts, data.v6_codes, int(ip) >> 64

    pos = bisect.bisect_right(starts, key) - 1
    if pos < 0 or codes[pos] == 0:
        return None
    return data.codes[codes[pos]]


@log_time
@lru_cache(maxsize=GEOIP_CACHE_SIZE)
def get_country(address: str) -> str | None:
    """Return country name for IP address, None if it's unknown."""
    data = _load()
    if data is None:
        return None

    code = lookup_code(data, address)
    return get_country_name(code) if code else None
