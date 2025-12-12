# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2025  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pytest
from rich.text import Text

from src.tewi.torrent.models import TorrentFile, TorrentFilePriority
from src.tewi.ui.util import get_file_list, print_priority


class TestPrintPriority:
    """Test cases for print_priority function."""

    @pytest.mark.parametrize("priority", list(TorrentFilePriority))
    def test_returns_non_empty_string(self, priority):
        """Test that all priorities return non-empty string values."""
        result = print_priority(priority)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unique_outputs(self):
        """Test that each priority level has a unique output."""
        results = [print_priority(p) for p in list(TorrentFilePriority)]
        assert len(results) == len(set(results))

    @pytest.mark.parametrize("priority", list(TorrentFilePriority))
    def test_rich_text_parseable(self, priority):
        """Test that outputs can be parsed by Rich Text."""
        result = print_priority(priority)
        # Should not raise an exception
        text = Text.from_markup(result)
        assert text is not None


class TestGetFileList:
    """Test cases for get_file_list function."""

    @pytest.mark.parametrize(
        "files,expected_file_count,expected_dir_count",
        [
            # Zero files
            ([], 0, 0),
            # One file
            (
                [
                    TorrentFile(
                        id=0,
                        name="file.txt",
                        size=1024,
                        completed=512,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                ],
                1,
                0,
            ),
            # 5 files flat (no directories)
            (
                [
                    TorrentFile(
                        id=0,
                        name="file1.txt",
                        size=1024,
                        completed=1024,
                        priority=TorrentFilePriority.HIGH,
                    ),
                    TorrentFile(
                        id=1,
                        name="file2.txt",
                        size=2048,
                        completed=0,
                        priority=TorrentFilePriority.NOT_DOWNLOADING,
                    ),
                    TorrentFile(
                        id=2,
                        name="file3.txt",
                        size=512,
                        completed=256,
                        priority=TorrentFilePriority.LOW,
                    ),
                    TorrentFile(
                        id=3,
                        name="file4.txt",
                        size=4096,
                        completed=4096,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                    TorrentFile(
                        id=4,
                        name="file5.txt",
                        size=8192,
                        completed=4096,
                        priority=TorrentFilePriority.HIGH,
                    ),
                ],
                5,
                0,
            ),
            # One dir with one file
            (
                [
                    TorrentFile(
                        id=0,
                        name="dir/file.txt",
                        size=1024,
                        completed=512,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                ],
                1,
                1,
            ),
            # Complex structure
            (
                [
                    TorrentFile(
                        id=0,
                        name="README.md",
                        size=1024,
                        completed=1024,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                    TorrentFile(
                        id=1,
                        name="src/main.py",
                        size=2048,
                        completed=1024,
                        priority=TorrentFilePriority.HIGH,
                    ),
                    TorrentFile(
                        id=2,
                        name="src/utils.py",
                        size=512,
                        completed=512,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                    TorrentFile(
                        id=3,
                        name="docs/guide.md",
                        size=4096,
                        completed=0,
                        priority=TorrentFilePriority.NOT_DOWNLOADING,
                    ),
                    TorrentFile(
                        id=4,
                        name="docs/api/index.html",
                        size=8192,
                        completed=4096,
                        priority=TorrentFilePriority.LOW,
                    ),
                    TorrentFile(
                        id=5,
                        name="docs/api/reference.html",
                        size=16384,
                        completed=16384,
                        priority=TorrentFilePriority.HIGH,
                    ),
                    TorrentFile(
                        id=6,
                        name="tests/test_one.py",
                        size=1536,
                        completed=768,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                    TorrentFile(
                        id=7,
                        name="tests/unit/test_two.py",
                        size=2560,
                        completed=2560,
                        priority=TorrentFilePriority.LOW,
                    ),
                    TorrentFile(
                        id=8,
                        name="tests/unit/fixtures/data.json",
                        size=128,
                        completed=64,
                        priority=TorrentFilePriority.HIGH,
                    ),
                    TorrentFile(
                        id=9,
                        name="LICENSE",
                        size=2048,
                        completed=2048,
                        priority=TorrentFilePriority.MEDIUM,
                    ),
                ],
                10,
                6,
            ),
        ],
        ids=[
            "zero_files",
            "one_file",
            "flat_files",
            "one_dir_one_file",
            "complex_structure",
        ],
    )
    def test_file_list_generation(
        self, files, expected_file_count, expected_dir_count
    ):
        """Test file list generation with various file structures."""
        result = get_file_list(files)

        # Verify the result is a list
        assert isinstance(result, list)

        # Verify all input files are present in the result
        file_ids = [item["id"] for item in result if item["is_file"]]
        expected_ids = {f.id for f in files}
        assert set(file_ids) == expected_ids
        assert len(file_ids) == expected_file_count

        # Verify directory entries
        directories = [item for item in result if not item["is_file"]]
        assert len(directories) == expected_dir_count

        # Verify total entry count
        if expected_dir_count > 0:
            # Should have more entries than input files (includes directories)
            assert len(result) > len(files)
        else:
            # Should have same number of entries as input files
            assert len(result) == len(files)

        # Verify directory entries have None values for file-specific fields
        for directory in directories:
            assert directory["id"] is None
            assert directory["size"] is None
            assert directory["done"] is None
            assert directory["priority"] is None

        # Verify all entries have proper structure
        for item in result:
            assert "is_file" in item
            assert "display_name" in item
            assert "id" in item
            assert "size" in item
            assert "done" in item
            assert "priority" in item

        # Verify file metadata is correctly formatted
        file_entries = [item for item in result if item["is_file"]]
        for entry in file_entries:
            # Size should be formatted string
            assert isinstance(entry["size"], str)
            # Done should be percentage string
            assert isinstance(entry["done"], str)
            assert entry["done"].endswith("%")
            # Priority should be string
            assert isinstance(entry["priority"], str)

        # Verify completion percentages are calculated correctly
        for file_dto in files:
            file_entry = next(
                item
                for item in result
                if item["is_file"] and item["id"] == file_dto.id
            )
            expected_percentage = int(
                (file_dto.completed / file_dto.size) * 100
            )
            assert file_entry["done"] == f"{expected_percentage}%"
