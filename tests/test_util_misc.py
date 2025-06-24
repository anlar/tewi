from src.tewi.util.misc import is_torrent_link


class TestIsTorrentLink:
    """Test cases for is_torrent_link function."""

    def test_magnet_links(self):
        """Test that magnet URIs are correctly identified."""
        magnet_uri = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
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
        assert is_torrent_link("this contains http:// but not at start") is False

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
        """Test that the function handles different cases correctly."""
        # These should work (lowercase)
        assert is_torrent_link("magnet:?xt=urn:btih:123") is True
        assert is_torrent_link("http://example.com") is True
        assert is_torrent_link("https://example.com") is True

        # These should not work (uppercase/mixed case)
        assert is_torrent_link("MAGNET:?xt=urn:btih:123") is False
        assert is_torrent_link("HTTP://example.com") is False
        assert is_torrent_link("HTTPS://example.com") is False
        assert is_torrent_link("Magnet:?xt=urn:btih:123") is False

    def test_real_world_examples(self):
        """Test with realistic torrent links."""
        # Real-world magnet link structure
        real_magnet = ("magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
                       "&dn=Example+Torrent&tr=udp%3A%2F%2Ftracker.example.com%3A80")
        assert is_torrent_link(real_magnet) is True

        # Common torrent site patterns
        assert is_torrent_link("https://torrents.example.com/download.php?id=12345") is True
        assert is_torrent_link("http://tracker.site.org/announce?passkey=abc123") is True
