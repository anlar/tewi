"""Unit tests for category detection logic in search providers."""

from src.tewi.service.search.base_provider import BaseSearchProvider
from src.tewi.common import TorrentCategory, SearchResultDTO


class DummyProvider(BaseSearchProvider):
    """Dummy provider for testing base class functionality."""

    def id(self) -> str:
        return "dummy"

    @property
    def short_name(self) -> str:
        return "Dummy"

    @property
    def full_name(self) -> str:
        return "Dummy Provider"

    def _search_impl(self, query: str) -> list[SearchResultDTO]:
        """Dummy implementation - not used in these tests."""
        return []


class TestCategoryDetection:
    """Test category detection from torrent names."""

    def setup_method(self):
        """Create a dummy provider instance for testing."""
        self.provider = DummyProvider()

    def test_detect_audio_by_extension(self):
        """Test detection of audio category by file extension."""
        assert self.provider._detect_category_from_name(
            "Artist - Album (2024) [FLAC].zip"
        ) == TorrentCategory.AUDIO

        assert self.provider._detect_category_from_name(
            "Song.mp3"
        ) == TorrentCategory.AUDIO

        assert self.provider._detect_category_from_name(
            "Soundtrack.m4a"
        ) == TorrentCategory.AUDIO

    def test_detect_audio_by_keyword(self):
        """Test detection of audio category by keyword."""
        assert self.provider._detect_category_from_name(
            "Artist Discography 1990-2024"
        ) == TorrentCategory.AUDIO

        assert self.provider._detect_category_from_name(
            "Game Soundtrack OST"
        ) == TorrentCategory.AUDIO

        assert self.provider._detect_category_from_name(
            "Music Collection"
        ) == TorrentCategory.AUDIO

    def test_detect_video_by_extension(self):
        """Test detection of video category by file extension."""
        assert self.provider._detect_category_from_name(
            "Movie.2024.mkv"
        ) == TorrentCategory.VIDEO

        assert self.provider._detect_category_from_name(
            "Series.S01E01.mp4"
        ) == TorrentCategory.VIDEO

        assert self.provider._detect_category_from_name(
            "Documentary.avi"
        ) == TorrentCategory.VIDEO

    def test_detect_video_by_keyword(self):
        """Test detection of video category by keyword."""
        assert self.provider._detect_category_from_name(
            "The Matrix (1999) 1080p BluRay x264"
        ) == TorrentCategory.VIDEO

        assert self.provider._detect_category_from_name(
            "Film Title 2024 4K HEVC"
        ) == TorrentCategory.VIDEO

        assert self.provider._detect_category_from_name(
            "Series S01 720p WEBRip"
        ) == TorrentCategory.VIDEO

    def test_detect_software_by_extension(self):
        """Test detection of software category by file extension."""
        assert self.provider._detect_category_from_name(
            "installer.exe"
        ) == TorrentCategory.SOFTWARE

        assert self.provider._detect_category_from_name(
            "application.dmg"
        ) == TorrentCategory.SOFTWARE

        assert self.provider._detect_category_from_name(
            "package.deb"
        ) == TorrentCategory.SOFTWARE

    def test_detect_software_by_keyword(self):
        """Test detection of software category by keyword."""
        assert self.provider._detect_category_from_name(
            "Adobe Software Suite 2024"
        ) == TorrentCategory.SOFTWARE

        assert self.provider._detect_category_from_name(
            "Program Setup Installer"
        ) == TorrentCategory.SOFTWARE

        assert self.provider._detect_category_from_name(
            "App Portable v1.0 + Crack"
        ) == TorrentCategory.SOFTWARE

    def test_detect_games_by_keyword(self):
        """Test detection of games category by keyword."""
        assert self.provider._detect_category_from_name(
            "Game Title Repack FitGirl"
        ) == TorrentCategory.GAMES

        assert self.provider._detect_category_from_name(
            "PC Game CODEX"
        ) == TorrentCategory.GAMES

        assert self.provider._detect_category_from_name(
            "PlayStation 5 Game"
        ) == TorrentCategory.GAMES

        assert self.provider._detect_category_from_name(
            "Nintendo Switch Gameplay"
        ) == TorrentCategory.GAMES

    def test_detect_xxx_by_keyword(self):
        """Test detection of XXX category by keyword."""
        assert self.provider._detect_category_from_name(
            "Adult Content XXX"
        ) == TorrentCategory.XXX

        assert self.provider._detect_category_from_name(
            "18+ NSFW Collection"
        ) == TorrentCategory.XXX

    def test_detect_other_by_extension(self):
        """Test detection of OTHER category by file extension."""
        assert self.provider._detect_category_from_name(
            "Book Title.pdf"
        ) == TorrentCategory.OTHER

        assert self.provider._detect_category_from_name(
            "Novel.epub"
        ) == TorrentCategory.OTHER

        assert self.provider._detect_category_from_name(
            "Archive.zip"
        ) == TorrentCategory.OTHER

    def test_detect_other_by_keyword(self):
        """Test detection of OTHER category by keyword."""
        assert self.provider._detect_category_from_name(
            "Programming Ebook Collection"
        ) == TorrentCategory.OTHER

        assert self.provider._detect_category_from_name(
            "Magazine Archive 2024"
        ) == TorrentCategory.OTHER

        assert self.provider._detect_category_from_name(
            "Comic Book Series"
        ) == TorrentCategory.OTHER

    def test_no_detection_returns_none(self):
        """Test that unrecognizable names return None."""
        assert self.provider._detect_category_from_name(
            "Random Title Without Keywords"
        ) is None

        assert self.provider._detect_category_from_name(
            "Something 2024"
        ) is None

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive."""
        assert self.provider._detect_category_from_name(
            "ALBUM.FLAC"
        ) == TorrentCategory.AUDIO

        assert self.provider._detect_category_from_name(
            "Movie.MKV"
        ) == TorrentCategory.VIDEO

        assert self.provider._detect_category_from_name(
            "GAME REPACK"
        ) == TorrentCategory.GAMES


class TestResultsRefinement:
    """Test refinement of search results with UNKNOWN categories."""

    def setup_method(self):
        """Create a dummy provider instance for testing."""
        self.provider = DummyProvider()

    def test_refine_unknown_categories(self):
        """Test that UNKNOWN categories are refined when possible."""
        results = [
            SearchResultDTO(
                title="Ubuntu 24.04 Desktop.iso",
                category=TorrentCategory.UNKNOWN,
                seeders=100,
                leechers=10,
                size=3000000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:abc123",
                info_hash="abc123",
                upload_date=None,
                provider="Test",
                provider_id="test"
            ),
            SearchResultDTO(
                title="Music Album [FLAC]",
                category=TorrentCategory.UNKNOWN,
                seeders=50,
                leechers=5,
                size=500000000,
                files_count=12,
                magnet_link="magnet:?xt=urn:btih:def456",
                info_hash="def456",
                upload_date=None,
                provider="Test",
                provider_id="test"
            ),
        ]

        refined = self.provider._refine_results(results)

        # First result should be detected as SOFTWARE (has .iso extension
        # but also "Desktop" keyword which could match software patterns)
        # Actually, "Ubuntu" and ".iso" don't match our patterns,
        # so it stays UNKNOWN
        assert refined[0].category == TorrentCategory.UNKNOWN

        # Second result should be detected as AUDIO
        assert refined[1].category == TorrentCategory.AUDIO

    def test_keep_known_categories_unchanged(self):
        """Test that non-UNKNOWN categories are not changed."""
        results = [
            SearchResultDTO(
                title="Movie Title 1080p",
                category=TorrentCategory.VIDEO,
                seeders=100,
                leechers=10,
                size=3000000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:abc123",
                info_hash="abc123",
                upload_date=None,
                provider="Test",
                provider_id="test"
            ),
        ]

        refined = self.provider._refine_results(results)

        # Category should remain VIDEO
        assert refined[0].category == TorrentCategory.VIDEO

    def test_preserve_unknown_when_no_detection(self):
        """Test that UNKNOWN is preserved when no pattern matches."""
        results = [
            SearchResultDTO(
                title="Random Content",
                category=TorrentCategory.UNKNOWN,
                seeders=10,
                leechers=1,
                size=100000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:xyz789",
                info_hash="xyz789",
                upload_date=None,
                provider="Test",
                provider_id="test"
            ),
        ]

        refined = self.provider._refine_results(results)

        # Should remain UNKNOWN
        assert refined[0].category == TorrentCategory.UNKNOWN

    def test_refinement_preserves_all_fields(self):
        """Test that refinement creates new DTO with all fields intact."""
        results = [
            SearchResultDTO(
                title="Movie 2024 1080p BluRay",
                category=TorrentCategory.UNKNOWN,
                seeders=100,
                leechers=10,
                size=3000000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:abc123",
                info_hash="abc123",
                upload_date=None,
                provider="Test",
                provider_id="test"
            ),
        ]

        refined = self.provider._refine_results(results)

        # Check all fields are preserved
        assert refined[0].title == "Movie 2024 1080p BluRay"
        assert refined[0].category == TorrentCategory.VIDEO  # Refined
        assert refined[0].seeders == 100
        assert refined[0].leechers == 10
        assert refined[0].size == 3000000000
        assert refined[0].files_count == 1
        assert refined[0].magnet_link == "magnet:?xt=urn:btih:abc123"
        assert refined[0].info_hash == "abc123"
        assert refined[0].upload_date is None
        assert refined[0].provider == "Test"
        assert refined[0].provider_id == "test"
