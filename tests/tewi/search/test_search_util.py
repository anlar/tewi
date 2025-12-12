"""Unit tests for search utility functions."""

from unittest.mock import MagicMock, patch

from src.tewi.search.models import StandardCategories
from src.tewi.search.util import (
    build_magnet_link,
    detect_category_from_name,
    urlopen,
)


class TestDetectCategoryFromName:
    """Test category detection from torrent names."""

    def test_detect_audio_by_extension(self):
        """Test detection of audio category by file extension."""
        assert (
            detect_category_from_name("Artist - Album (2024) [FLAC].zip")
            == StandardCategories.AUDIO
        )

        assert detect_category_from_name("Song.mp3") == StandardCategories.AUDIO

        assert (
            detect_category_from_name("Soundtrack.m4a")
            == StandardCategories.AUDIO
        )

    def test_detect_audio_by_keyword(self):
        """Test detection of audio category by keyword."""
        assert (
            detect_category_from_name("Artist Discography 1990-2024")
            == StandardCategories.AUDIO
        )

        assert (
            detect_category_from_name("Game Soundtrack OST")
            == StandardCategories.AUDIO
        )

        assert (
            detect_category_from_name("Music Collection")
            == StandardCategories.AUDIO
        )

    def test_detect_video_by_extension(self):
        """Test detection of video category by file extension."""
        assert (
            detect_category_from_name("Movie.2024.mkv")
            == StandardCategories.MOVIES
        )

        assert (
            detect_category_from_name("Series.S01E01.mp4")
            == StandardCategories.MOVIES
        )

        assert (
            detect_category_from_name("Documentary.avi")
            == StandardCategories.MOVIES
        )

    def test_detect_video_by_keyword(self):
        """Test detection of video category by keyword."""
        assert (
            detect_category_from_name("The Matrix (1999) 1080p BluRay x264")
            == StandardCategories.MOVIES
        )

        assert (
            detect_category_from_name("Film Title 2024 4K HEVC")
            == StandardCategories.MOVIES
        )

        assert (
            detect_category_from_name("Series S01 720p WEBRip")
            == StandardCategories.MOVIES
        )

    def test_detect_software_by_extension(self):
        """Test detection of software category by file extension."""
        assert (
            detect_category_from_name("installer.exe") == StandardCategories.PC
        )

        assert (
            detect_category_from_name("application.dmg")
            == StandardCategories.PC
        )

        assert detect_category_from_name("package.deb") == StandardCategories.PC

    def test_detect_software_by_keyword(self):
        """Test detection of software category by keyword."""
        assert (
            detect_category_from_name("Adobe Software Suite 2024")
            == StandardCategories.PC
        )

        assert (
            detect_category_from_name("Program Setup Installer")
            == StandardCategories.PC
        )

        assert (
            detect_category_from_name("App Portable v1.0 + Crack")
            == StandardCategories.PC
        )

    def test_detect_games_by_keyword(self):
        """Test detection of games category by keyword."""
        assert (
            detect_category_from_name("Game Title Repack FitGirl")
            == StandardCategories.CONSOLE
        )

        assert (
            detect_category_from_name("PC Game CODEX")
            == StandardCategories.CONSOLE
        )

        assert (
            detect_category_from_name("PlayStation 5 Game")
            == StandardCategories.CONSOLE
        )

        assert (
            detect_category_from_name("Nintendo Switch Gameplay")
            == StandardCategories.CONSOLE
        )

    def test_detect_xxx_by_keyword(self):
        """Test detection of XXX category by keyword."""
        assert (
            detect_category_from_name("Adult Content XXX")
            == StandardCategories.XXX
        )

        assert (
            detect_category_from_name("18+ NSFW Collection")
            == StandardCategories.XXX
        )

    def test_detect_other_by_extension(self):
        """Test detection of BOOKS category by file extension."""
        assert (
            detect_category_from_name("Book Title.pdf")
            == StandardCategories.BOOKS
        )

        assert (
            detect_category_from_name("Novel.epub") == StandardCategories.BOOKS
        )

        assert (
            detect_category_from_name("Archive.zip") == StandardCategories.BOOKS
        )

    def test_detect_other_by_keyword(self):
        """Test detection of BOOKS category by keyword."""
        assert (
            detect_category_from_name("Programming Ebook Collection")
            == StandardCategories.BOOKS
        )

        assert (
            detect_category_from_name("Magazine Archive 2024")
            == StandardCategories.BOOKS
        )

        assert (
            detect_category_from_name("Comic Book Series")
            == StandardCategories.BOOKS
        )

    def test_no_detection_returns_none(self):
        """Test that unrecognizable names return None."""
        assert (
            detect_category_from_name("Random Title Without Keywords") is None
        )

        assert detect_category_from_name("Something 2024") is None

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        assert (
            detect_category_from_name("ALBUM.FLAC") == StandardCategories.AUDIO
        )

        assert (
            detect_category_from_name("Movie.MKV") == StandardCategories.MOVIES
        )

        assert (
            detect_category_from_name("GAME REPACK")
            == StandardCategories.CONSOLE
        )


class TestBuildMagnetLink:
    """Test building magnet links."""

    def test_build_magnet_link_basic(self):
        """Test building a basic magnet link without trackers."""
        magnet = build_magnet_link(
            "abc123def456", "Test Torrent", trackers=None
        )

        assert magnet.startswith("magnet:?xt=urn:btih:abc123def456")
        assert "dn=Test%20Torrent" in magnet

    def test_build_magnet_link_with_special_chars(self):
        """Test building magnet link with special characters in name."""
        magnet = build_magnet_link(
            "abc123", "Test [2024] (1080p) & More!", trackers=None
        )

        assert "magnet:?xt=urn:btih:abc123" in magnet
        # Check that special characters are URL-encoded
        assert "Test%20" in magnet or "Test+" in magnet
        assert "%5B" in magnet or "[" not in magnet.split("&")[0]

    def test_build_magnet_link_with_trackers(self):
        """Test building magnet link with tracker URLs."""
        trackers = [
            "http://tracker1.example.com:80/announce",
            "udp://tracker2.example.com:6969/announce",
        ]

        magnet = build_magnet_link("abc123", "Test", trackers=trackers)

        assert "magnet:?xt=urn:btih:abc123" in magnet
        assert "dn=Test" in magnet
        assert "tr=http://tracker1.example.com:80/announce" in magnet
        assert "tr=udp://tracker2.example.com:6969/announce" in magnet

    def test_build_magnet_link_empty_trackers(self):
        """Test building magnet link with empty tracker list."""
        magnet = build_magnet_link("abc123", "Test", trackers=[])

        assert magnet == "magnet:?xt=urn:btih:abc123&dn=Test"


class TestUrlopen:
    """Test URL opening with User-Agent header."""

    @patch("src.tewi.search.util.urllib.request.urlopen")
    @patch("src.tewi.search.util.urllib.request.Request")
    def test_urlopen_adds_user_agent(self, mock_request_class, mock_urlopen):
        """Test that urlopen adds User-Agent header."""
        mock_request = MagicMock()
        mock_request_class.return_value = mock_request

        urlopen("http://example.com")

        # Verify Request was created with URL
        mock_request_class.assert_called_once_with("http://example.com")

        # Verify User-Agent header was added
        mock_request.add_header.assert_called_once()
        call_args = mock_request.add_header.call_args[0]
        assert call_args[0] == "User-Agent"
        assert "Mozilla" in call_args[1]

        # Verify urlopen was called with request
        mock_urlopen.assert_called_once()

    @patch("src.tewi.search.util.urllib.request.urlopen")
    @patch("src.tewi.search.util.urllib.request.Request")
    def test_urlopen_respects_timeout(self, mock_request_class, mock_urlopen):
        """Test that urlopen respects timeout parameter."""
        mock_request = MagicMock()
        mock_request_class.return_value = mock_request

        urlopen("http://example.com", timeout=60)

        # Verify urlopen was called with timeout
        mock_urlopen.assert_called_once()
        call_kwargs = mock_urlopen.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("src.tewi.search.util.urllib.request.urlopen")
    @patch("src.tewi.search.util.urllib.request.Request")
    def test_urlopen_default_timeout(self, mock_request_class, mock_urlopen):
        """Test that urlopen uses default timeout of 30 seconds."""
        mock_request = MagicMock()
        mock_request_class.return_value = mock_request

        urlopen("http://example.com")

        # Verify urlopen was called with default timeout
        mock_urlopen.assert_called_once()
        call_kwargs = mock_urlopen.call_args[1]
        assert call_kwargs["timeout"] == 30
