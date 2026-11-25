import base64
import dataclasses

import pytest

from src.tewi.util.misc import (
    RemoteData,
    is_http_url,
    is_safe_name,
    is_torrent_hash,
    is_torrent_link,
    normalize_torrent_hash,
    parse_count,
)

# Names with shell syntax, which "compgen -W" in bash completion would
# expand, or path separators
UNSAFE_NAMES = [
    "",
    "$(touch PWNED)",
    "a$(id)",
    "`id`",
    "${HOME}",
    "my profile",
    "a;b",
    "../x",
    "a/b",
    "-x",
    ".hidden",
    "name\n",
    "naïve",
]


class TestIsSafeName:
    """Test cases for is_safe_name function."""

    @pytest.mark.parametrize(
        "name", ["home", "Seed_Box", "nas-2", "v1.2", "9", "textual-dark"]
    )
    def test_safe_names(self, name):
        assert is_safe_name(name) is True

    @pytest.mark.parametrize("name", UNSAFE_NAMES)
    def test_unsafe_names(self, name):
        assert is_safe_name(name) is False


class TestIsTorrentLink:
    """Test cases for is_torrent_link function."""

    def test_magnet_links(self):
        """Test that magnet URIs are correctly identified."""
        magnet_uri = (
            "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        )
        assert is_torrent_link(magnet_uri) is True

        # Test with additional parameters
        complex_magnet = "magnet:?xt=urn:btih:abcd&dn=test.torrent&tr=http://tracker.example.com"
        assert is_torrent_link(complex_magnet) is True

    def test_http_links(self):
        """Test that HTTP URLs are correctly identified."""
        http_url = "http://example.com/test.torrent"
        assert is_torrent_link(http_url) is True

        # Test with query parameters
        http_with_params = "http://tracker.example.com/download?id=123&key=abc"
        assert is_torrent_link(http_with_params) is True

    def test_https_links(self):
        """Test that HTTPS URLs are correctly identified."""
        https_url = "https://example.com/test.torrent"
        assert is_torrent_link(https_url) is True

        # Test with complex path
        https_complex = "https://secure.tracker.com/torrents/download/12345"
        assert is_torrent_link(https_complex) is True

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled correctly."""
        # Leading whitespace
        assert is_torrent_link("  magnet:?xt=urn:btih:123") is True
        assert is_torrent_link("\thttp://example.com/test.torrent") is True
        assert is_torrent_link("\nhttps://example.com/test.torrent") is True

        # Trailing whitespace
        assert is_torrent_link("magnet:?xt=urn:btih:123  ") is True
        assert is_torrent_link("http://example.com/test.torrent\t") is True
        assert is_torrent_link("https://example.com/test.torrent\n") is True

        # Both leading and trailing
        assert is_torrent_link("  magnet:?xt=urn:btih:123  ") is True

    def test_non_torrent_links(self):
        """Test that non-torrent text is correctly rejected."""
        # Plain text
        assert is_torrent_link("just some text") is False
        assert is_torrent_link("test.torrent") is False

        # Other protocols
        assert is_torrent_link("ftp://example.com/file.torrent") is False
        assert is_torrent_link("file:///path/to/file.torrent") is False

        # Partial matches
        assert is_torrent_link("not a magnet: link") is False
        assert (
            is_torrent_link("this contains http:// but not at start") is False
        )

    def test_empty_and_edge_cases(self):
        """Test edge cases like empty strings and whitespace-only strings."""
        assert is_torrent_link("") is False
        assert is_torrent_link("   ") is False
        assert is_torrent_link("\t\n") is False

        # Just the protocol without anything else
        assert is_torrent_link("magnet:") is True
        assert is_torrent_link("http://") is True
        assert is_torrent_link("https://") is True

    def test_case_sensitivity(self):
        """Test that the function is case-insensitive."""
        # Lowercase should work
        assert is_torrent_link("magnet:?xt=urn:btih:123") is True
        assert is_torrent_link("http://example.com") is True
        assert is_torrent_link("https://example.com") is True

        # Uppercase should also work (case-insensitive)
        assert is_torrent_link("MAGNET:?xt=urn:btih:123") is True
        assert is_torrent_link("HTTP://example.com") is True
        assert is_torrent_link("HTTPS://example.com") is True
        assert is_torrent_link("Magnet:?xt=urn:btih:123") is True
        assert is_torrent_link("HtTp://example.com") is True
        assert is_torrent_link("HtTpS://example.com") is True

    def test_real_world_examples(self):
        """Test with realistic torrent links."""
        # Real-world magnet link structure
        real_magnet = (
            "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
            "&dn=Example+Torrent&tr=udp%3A%2F%2Ftracker.example.com%3A80"
        )
        assert is_torrent_link(real_magnet) is True

        # Common torrent site patterns
        assert (
            is_torrent_link(
                "https://torrents.example.com/download.php?id=12345"
            )
            is True
        )
        assert (
            is_torrent_link("http://tracker.site.org/announce?passkey=abc123")
            is True
        )


class TestIsHttpUrl:
    """Test cases for is_http_url function."""

    def test_plain_urls(self):
        """Test that bare HTTP(S) URLs are recognized."""
        assert is_http_url("http://example.com") is True
        assert is_http_url("https://example.com/torrent/123") is True
        assert is_http_url("https://example.com/t?id=1&key=abc#frag") is True

    def test_case_insensitive_scheme(self):
        """Test that scheme case is ignored."""
        assert is_http_url("HTTPS://example.com") is True
        assert is_http_url("Http://example.com") is True

    def test_whitespace_handling(self):
        """Test that surrounding whitespace is stripped."""
        assert is_http_url("  https://example.com  ") is True
        assert is_http_url("\thttp://example.com\n") is True

    def test_url_with_other_text(self):
        """Test that URLs mixed with other text are rejected."""
        assert is_http_url("Visit https://example.com") is False
        assert is_http_url("https://example.com for details") is False
        assert is_http_url("https://example.com https://example.org") is False

    def test_non_http_values(self):
        """Test that non-HTTP text is rejected."""
        assert is_http_url("") is False
        assert is_http_url("   ") is False
        assert is_http_url("Created by some tool") is False
        assert is_http_url("ftp://example.com/file") is False
        assert is_http_url("magnet:?xt=urn:btih:abcd") is False
        assert is_http_url("example.com") is False


class TestIsTorrentHash:
    """Test cases for is_torrent_hash function."""

    def test_hex_hash(self):
        """Test that a 40-char hex info hash is recognized."""
        hex_hash = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
        assert is_torrent_hash(hex_hash) is True
        assert is_torrent_hash(hex_hash.upper()) is True

    def test_base32_hash(self):
        """Test that a 32-char Base32 info hash is recognized."""
        base32_hash = "MFRGG2LTMVZW443UOJUW4ZLTMVXHI2LM"
        assert is_torrent_hash(base32_hash) is True

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is stripped."""
        hex_hash = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
        assert is_torrent_hash(f"  {hex_hash}  ") is True

    def test_wrong_length(self):
        """Test that strings of the wrong length are rejected."""
        assert (
            is_torrent_hash("c12fe1c06bba254a9dc9f519b335aa7c1367a88") is False
        )
        assert (
            is_torrent_hash("c12fe1c06bba254a9dc9f519b335aa7c1367a88aa")
            is False
        )

    def test_non_hash_values(self):
        """Test that non-hash text is rejected."""
        assert is_torrent_hash("") is False
        assert is_torrent_hash("   ") is False
        assert is_torrent_hash("not-a-hash") is False
        assert (
            is_torrent_hash(
                "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
            )
            is False
        )
        assert is_torrent_hash("~/downloads/file.torrent") is False


class TestNormalizeTorrentHash:
    """Test cases for normalize_torrent_hash function."""

    HEX = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"

    def test_hex_is_lowercased(self):
        assert normalize_torrent_hash(self.HEX.upper()) == self.HEX
        assert normalize_torrent_hash(self.HEX) == self.HEX

    def test_whitespace_is_stripped(self):
        assert normalize_torrent_hash(f"  {self.HEX}  ") == self.HEX

    def test_base32_is_converted_to_hex(self):
        base32 = base64.b32encode(bytes.fromhex(self.HEX)).decode()
        assert normalize_torrent_hash(base32) == self.HEX
        assert normalize_torrent_hash(base32.lower()) == self.HEX

    @pytest.mark.parametrize(
        "value", ["", "abc", "not-a-hash", HEX + "&tr=udp://x:1"]
    )
    def test_non_hash_is_unchanged(self, value):
        assert normalize_torrent_hash(value) == value


class TestParseCount:
    """Test cases for parse_count function."""

    @pytest.mark.parametrize(
        "value, expected",
        [(0, 0), (12, 12), ("12", 12), (" 7 ", 7)],
    )
    def test_valid_count(self, value, expected):
        assert parse_count(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            None,
            True,
            False,
            -1,
            "",
            "-1",
            "1.5",
            "1,234",
            "N/A",
            "[b]1[/]",
            "[@click=app.pwn()]42[/]",
            "[/oops]",
            "1.5 GB",
            1.5,
            [42],
            {"value": 42},
        ],
    )
    def test_invalid_count_is_none(self, value):
        assert parse_count(value) is None


@dataclasses.dataclass(frozen=True)
class _Remote(RemoteData):
    name: str
    names: list[str]
    pairs: list[tuple[str, int]]


@dataclasses.dataclass(frozen=True)
class _RemoteWithPostInit(RemoteData):
    name: str
    upper: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "upper", self.name.upper())


class TestRemoteData:
    """Test cases for RemoteData base class."""

    def test_control_chars_are_removed(self):
        obj = _Remote("a\x1b[31mb", ["c\x07"], [("d\x1b", 1)])

        assert obj == _Remote("a[31mb", ["c"], [("d", 1)])

    def test_line_breaks_and_tabs_are_kept(self):
        assert _Remote("a\n\tb", [], []).name == "a\n\tb"

    def test_subclass_post_init_runs_after_cleaning(self):
        obj = _RemoteWithPostInit("a\x1bb")

        assert obj.name == "ab"
        assert obj.upper == "AB"
