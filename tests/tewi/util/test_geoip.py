import gzip
import importlib.util
import io
import ipaddress
import urllib.error
from pathlib import Path

import pytest

import src.tewi.util.geoip as geoip_module
from src.tewi.util.countries import COUNTRY_NAMES, get_country_name
from src.tewi.util.geoip import get_country, lookup_code, parse_data

_BUILD_SCRIPT = Path(__file__).parents[3] / "package" / "build_geoip.py"
_spec = importlib.util.spec_from_file_location("build_geoip", _BUILD_SCRIPT)
build_geoip = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_geoip)

V4_CSV = b"""16777216,16777471,AU
16777472,16778239,CN
16778240,16779263,AU
134744064,134744319,US
134744320,134744575,US
3221225472,3221225727,DE
4294967040,4294967295,JP
"""


def _csv(*networks: tuple[str, str]) -> bytes:
    rows = []
    for network, country in networks:
        net = ipaddress.ip_network(network)
        rows.append(f"{int(net[0])},{int(net[-1])},{country}\n")
    return "".join(rows).encode("ascii")


# Sub-/64 range 2a03::/96 followed by gap
V6_CSV = _csv(
    ("2001:4860::/32", "US"),
    ("2a02:6b8::/32", "RU"),
    ("2a03::/96", "DE"),
)


def _data():
    return parse_data(build_geoip.encode("2026-11-05", V4_CSV, V6_CSV))


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestDownload:
    """Test cases for data download retries."""

    @pytest.fixture
    def urlopen(self, monkeypatch):
        """Replace urlopen with fake failing with given HTTP codes first."""
        calls = []

        def setup(*codes):
            def fake(request, timeout):
                calls.append(request.full_url)
                if len(calls) <= len(codes):
                    raise urllib.error.HTTPError(
                        request.full_url, codes[len(calls) - 1], "", {}, None
                    )
                return _Response(b"data")

            monkeypatch.setattr(build_geoip.urllib.request, "urlopen", fake)
            return calls

        monkeypatch.setattr(build_geoip, "RETRY_DELAY", 0)
        return setup

    def test_retry_on_server_error(self, urlopen):
        calls = urlopen(504, 503)
        assert build_geoip.download("https://example.org/", "*/*") == b"data"
        assert len(calls) == 3

    def test_give_up_after_attempts(self, urlopen):
        calls = urlopen(504, 504, 504)
        with pytest.raises(urllib.error.HTTPError):
            build_geoip.download("https://example.org/", "*/*")
        assert len(calls) == build_geoip.ATTEMPTS

    def test_no_retry_on_client_error(self, urlopen):
        calls = urlopen(404)
        with pytest.raises(urllib.error.HTTPError):
            build_geoip.download("https://example.org/", "*/*")
        assert len(calls) == 1

    def test_only_https(self, urlopen):
        calls = urlopen()
        with pytest.raises(ValueError, match="HTTPS"):
            build_geoip.download("http://example.org/", "*/*")
        assert calls == []


class TestBuildRanges:
    """Test cases for converting CSV rows to range starts."""

    def test_gaps_and_merging(self):
        codes = {"--": 0}
        rows = [("10", "19", "US"), ("20", "29", "US"), ("40", "49", "DE")]
        starts, indexes = build_geoip.build_ranges(rows, 0, codes)
        assert starts == [0, 10, 30, 40, 50]
        assert indexes == [0, 1, 0, 2, 0]

    def test_shift_range_covers_whole_block(self):
        codes = {"--": 0}
        block = 1 << 64
        rows = [(str(block), str(block + 100), "DE")]
        starts, indexes = build_geoip.build_ranges(rows, 64, codes)
        assert starts == [0, 1, 2]
        assert indexes == [0, 1, 0]

    def test_shift_later_range_replaces_earlier_one(self):
        codes = {"--": 0}
        block = 1 << 64
        rows = [
            (str(block), str(block + 9), "DE"),
            (str(block + 10), str(2 * block - 1), "FR"),
        ]
        starts, indexes = build_geoip.build_ranges(rows, 64, codes)
        assert starts == [0, 1, 2]
        assert indexes == [0, codes["FR"], 0]

    def test_overlapping_ranges_fail(self):
        rows = [("10", "19", "US"), ("15", "29", "DE")]
        with pytest.raises(ValueError, match="overlap"):
            build_geoip.build_ranges(rows, 0, {"--": 0})

    def test_unsorted_ranges_fail(self):
        rows = [("20", "29", "US"), ("10", "19", "DE")]
        with pytest.raises(ValueError, match="not sorted"):
            build_geoip.build_ranges(rows, 0, {"--": 0})

    @pytest.mark.parametrize("country", ["us", "USA", "", "1A"])
    def test_invalid_country_code_fails(self, country):
        rows = [("10", "19", country)]
        with pytest.raises(ValueError, match="Invalid country code"):
            build_geoip.build_ranges(rows, 0, {"--": 0})


class TestParseData:
    """Test cases for data file parsing."""

    def test_roundtrip(self):
        data = _data()
        assert data.date == "2026-11-05"
        assert data.codes[0] == "--"
        assert set(data.codes[1:]) == {"AU", "CN", "US", "DE", "JP", "RU"}
        # Adjacent US ranges are merged, range up to the last address
        # doesn't add trailing gap
        assert list(data.v4_starts) == [
            0,
            16777216,
            16777472,
            16778240,
            16779264,
            134744064,
            134744576,
            3221225472,
            3221225728,
            4294967040,
        ]

    def test_bad_magic(self):
        raw = build_geoip.encode("2026-11-05", V4_CSV, V6_CSV)
        with pytest.raises(ValueError, match="unsupported"):
            parse_data(b"X" + raw[1:])

    def test_truncated(self):
        raw = build_geoip.encode("2026-11-05", V4_CSV, V6_CSV)
        with pytest.raises(ValueError, match="truncated"):
            parse_data(raw[:-1])
        with pytest.raises(ValueError, match="truncated"):
            parse_data(raw[:10])

    def test_trailing_bytes(self):
        raw = build_geoip.encode("2026-11-05", V4_CSV, V6_CSV)
        with pytest.raises(ValueError, match="trailing"):
            parse_data(raw + b"\0")


class TestLookupCode:
    """Test cases for country code lookup."""

    @pytest.mark.parametrize(
        "address,code",
        [
            ("1.0.0.0", "AU"),
            ("1.0.1.255", "CN"),
            ("1.0.4.0", "AU"),
            ("8.8.8.8", "US"),
            ("8.8.9.255", "US"),
            ("192.0.0.1", "DE"),
            ("255.255.255.255", "JP"),
            ("2001:4860:4860::8888", "US"),
            ("2a02:6b8::feed:ff", "RU"),
            ("2a03::1", "DE"),
            ("::ffff:8.8.8.8", "US"),
        ],
    )
    def test_known(self, address, code):
        assert lookup_code(_data(), address) == code

    @pytest.mark.parametrize(
        "address",
        [
            "0.0.0.0",
            "0.255.255.255",
            "1.0.8.0",
            "8.8.10.0",
            "192.168.1.1",
            "::1",
            "2a03:0:0:1::1",
            "ffff::1",
            "",
            "not an address",
            "1.2.3.4:51413",
        ],
    )
    def test_unknown(self, address):
        assert lookup_code(_data(), address) is None


class TestGetCountry:
    """Test cases for get_country function."""

    @pytest.fixture
    def data_file(self, tmp_path, monkeypatch):
        path = tmp_path / "geoip.dat.gz"
        monkeypatch.setattr(geoip_module, "DATA_FILE", path)
        geoip_module._load.cache_clear()
        get_country.__wrapped__.cache_clear()
        yield path
        geoip_module._load.cache_clear()
        get_country.__wrapped__.cache_clear()

    def test_country_name(self, data_file):
        data_file.write_bytes(
            gzip.compress(build_geoip.encode("2026-11-05", V4_CSV, V6_CSV))
        )
        assert get_country("8.8.8.8") == "United States"
        assert get_country("2a02:6b8::1") == "Russia"
        assert get_country("192.168.1.1") is None

    def test_missing_file(self, data_file):
        assert get_country("8.8.8.8") is None

    def test_corrupted_file(self, data_file):
        data_file.write_bytes(b"not gzip")
        assert get_country("8.8.8.8") is None


class TestCountryNames:
    """Test cases for country name table."""

    def test_known_code(self):
        assert get_country_name("US") == "United States"
        assert get_country_name("de") == "Germany"

    def test_unknown_code(self):
        assert get_country_name("zz") == "ZZ"

    def test_codes_are_valid(self):
        assert all(
            len(c) == 2 and c.isascii() and c.isupper() for c in COUNTRY_NAMES
        )
        assert all(COUNTRY_NAMES.values())
