"""Unit tests for category detection logic in search providers."""

from src.tewi.service.search.base_provider import BaseSearchProvider
from src.tewi.common import SearchResultDTO, JackettCategories


class DummyProvider(BaseSearchProvider):
    """Dummy provider for testing base class functionality."""

    def id(self) -> str:
        return "dummy"

    @property
    def name(self) -> str:
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
        ) == JackettCategories.AUDIO

        assert self.provider._detect_category_from_name(
            "Song.mp3"
        ) == JackettCategories.AUDIO

        assert self.provider._detect_category_from_name(
            "Soundtrack.m4a"
        ) == JackettCategories.AUDIO

    def test_detect_audio_by_keyword(self):
        """Test detection of audio category by keyword."""
        assert self.provider._detect_category_from_name(
            "Artist Discography 1990-2024"
        ) == JackettCategories.AUDIO

        assert self.provider._detect_category_from_name(
            "Game Soundtrack OST"
        ) == JackettCategories.AUDIO

        assert self.provider._detect_category_from_name(
            "Music Collection"
        ) == JackettCategories.AUDIO

    def test_detect_video_by_extension(self):
        """Test detection of video category by file extension."""
        assert self.provider._detect_category_from_name(
            "Movie.2024.mkv"
        ) == JackettCategories.MOVIES

        assert self.provider._detect_category_from_name(
            "Series.S01E01.mp4"
        ) == JackettCategories.MOVIES

        assert self.provider._detect_category_from_name(
            "Documentary.avi"
        ) == JackettCategories.MOVIES

    def test_detect_video_by_keyword(self):
        """Test detection of video category by keyword."""
        assert self.provider._detect_category_from_name(
            "The Matrix (1999) 1080p BluRay x264"
        ) == JackettCategories.MOVIES

        assert self.provider._detect_category_from_name(
            "Film Title 2024 4K HEVC"
        ) == JackettCategories.MOVIES

        assert self.provider._detect_category_from_name(
            "Series S01 720p WEBRip"
        ) == JackettCategories.MOVIES

    def test_detect_software_by_extension(self):
        """Test detection of software category by file extension."""
        assert self.provider._detect_category_from_name(
            "installer.exe"
        ) == JackettCategories.PC

        assert self.provider._detect_category_from_name(
            "application.dmg"
        ) == JackettCategories.PC

        assert self.provider._detect_category_from_name(
            "package.deb"
        ) == JackettCategories.PC

    def test_detect_software_by_keyword(self):
        """Test detection of software category by keyword."""
        assert self.provider._detect_category_from_name(
            "Adobe Software Suite 2024"
        ) == JackettCategories.PC

        assert self.provider._detect_category_from_name(
            "Program Setup Installer"
        ) == JackettCategories.PC

        assert self.provider._detect_category_from_name(
            "App Portable v1.0 + Crack"
        ) == JackettCategories.PC

    def test_detect_games_by_keyword(self):
        """Test detection of games category by keyword."""
        assert self.provider._detect_category_from_name(
            "Game Title Repack FitGirl"
        ) == JackettCategories.CONSOLE

        assert self.provider._detect_category_from_name(
            "PC Game CODEX"
        ) == JackettCategories.CONSOLE

        assert self.provider._detect_category_from_name(
            "PlayStation 5 Game"
        ) == JackettCategories.CONSOLE

        assert self.provider._detect_category_from_name(
            "Nintendo Switch Gameplay"
        ) == JackettCategories.CONSOLE

    def test_detect_xxx_by_keyword(self):
        """Test detection of XXX category by keyword."""
        assert self.provider._detect_category_from_name(
            "Adult Content XXX"
        ) == JackettCategories.XXX

        assert self.provider._detect_category_from_name(
            "18+ NSFW Collection"
        ) == JackettCategories.XXX

    def test_detect_other_by_extension(self):
        """Test detection of BOOKS category by file extension."""
        assert self.provider._detect_category_from_name(
            "Book Title.pdf"
        ) == JackettCategories.BOOKS

        assert self.provider._detect_category_from_name(
            "Novel.epub"
        ) == JackettCategories.BOOKS

        assert self.provider._detect_category_from_name(
            "Archive.zip"
        ) == JackettCategories.BOOKS

    def test_detect_other_by_keyword(self):
        """Test detection of BOOKS category by keyword."""
        assert self.provider._detect_category_from_name(
            "Programming Ebook Collection"
        ) == JackettCategories.BOOKS

        assert self.provider._detect_category_from_name(
            "Magazine Archive 2024"
        ) == JackettCategories.BOOKS

        assert self.provider._detect_category_from_name(
            "Comic Book Series"
        ) == JackettCategories.BOOKS

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
        ) == JackettCategories.AUDIO

        assert self.provider._detect_category_from_name(
            "Movie.MKV"
        ) == JackettCategories.MOVIES

        assert self.provider._detect_category_from_name(
            "GAME REPACK"
        ) == JackettCategories.CONSOLE


class TestResultsRefinement:
    """Test refinement of search results with UNKNOWN categories."""

    def setup_method(self):
        """Create a dummy provider instance for testing."""
        self.provider = DummyProvider()

    def test_refine_unknown_categories(self):
        """Test that empty categories are refined when possible."""
        results = [
            SearchResultDTO(
                title="Ubuntu 24.04 Desktop.iso",
                categories=[],
                seeders=100,
                leechers=10,
                size=3000000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:abc123",
                info_hash="abc123",
                upload_date=None,
                provider="Test",
                provider_id="test",
                torrent_link=None
            ),
            SearchResultDTO(
                title="Music Album [FLAC]",
                categories=[],
                seeders=50,
                leechers=5,
                size=500000000,
                files_count=12,
                magnet_link="magnet:?xt=urn:btih:def456",
                info_hash="def456",
                upload_date=None,
                provider="Test",
                provider_id="test",
                torrent_link=None
            ),
        ]

        refined = self.provider._refine_results(results)

        # First result should remain empty (no pattern matches)
        assert refined[0].categories == []

        # Second result should be detected as AUDIO
        assert len(refined[1].categories) == 1
        assert refined[1].categories[0] == JackettCategories.AUDIO

    def test_keep_known_categories_unchanged(self):
        """Test that non-empty categories are not changed."""
        results = [
            SearchResultDTO(
                title="Movie Title 1080p",
                categories=[JackettCategories.MOVIES],
                seeders=100,
                leechers=10,
                size=3000000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:abc123",
                info_hash="abc123",
                upload_date=None,
                provider="Test",
                provider_id="test",
                torrent_link=None
            ),
        ]

        refined = self.provider._refine_results(results)

        # Category should remain Movies
        assert len(refined[0].categories) == 1
        assert refined[0].categories[0] == JackettCategories.MOVIES

    def test_preserve_unknown_when_no_detection(self):
        """Test that empty categories are preserved when no pattern matches."""
        results = [
            SearchResultDTO(
                title="Random Content",
                categories=[],
                seeders=10,
                leechers=1,
                size=100000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:xyz789",
                info_hash="xyz789",
                upload_date=None,
                provider="Test",
                provider_id="test",
                torrent_link=None
            ),
        ]

        refined = self.provider._refine_results(results)

        # Should remain empty
        assert refined[0].categories == []

    def test_refinement_preserves_all_fields(self):
        """Test that refinement creates new DTO with all fields intact."""
        results = [
            SearchResultDTO(
                title="Movie 2024 1080p BluRay",
                categories=[],
                seeders=100,
                leechers=10,
                size=3000000000,
                files_count=1,
                magnet_link="magnet:?xt=urn:btih:abc123",
                info_hash="abc123",
                upload_date=None,
                provider="Test",
                provider_id="test",
                torrent_link=None
            ),
        ]

        refined = self.provider._refine_results(results)

        # Check all fields are preserved
        assert refined[0].title == "Movie 2024 1080p BluRay"
        # Should be refined to Movies category
        assert len(refined[0].categories) == 1
        assert refined[0].categories[0] == JackettCategories.MOVIES
        assert refined[0].seeders == 100
        assert refined[0].leechers == 10
        assert refined[0].size == 3000000000
        assert refined[0].files_count == 1
        assert refined[0].magnet_link == "magnet:?xt=urn:btih:abc123"
        assert refined[0].info_hash == "abc123"
        assert refined[0].upload_date is None
        assert refined[0].provider == "Test"
        assert refined[0].provider_id == "test"
        assert refined[0].torrent_link is None
