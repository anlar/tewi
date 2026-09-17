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

from src.tewi.torrent.models import TorrentFile, TorrentFilePriority
from src.tewi.ui.panel.details import FileSelectionState, TorrentInfoPanel


@pytest.fixture
def priority_display():
    """Create priority display mapping for testing."""
    return {
        TorrentFilePriority.NOT_DOWNLOADING: "[dim]-[/]",
        TorrentFilePriority.LOW: "[dim yellow]↓[/]",
        TorrentFilePriority.MEDIUM: "→",
        TorrentFilePriority.HIGH: "[bold red]↑[/]",
    }


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
        self, priority_display, files, expected_file_count, expected_dir_count
    ):
        """Test file list generation with various file structures."""
        result = TorrentInfoPanel.get_file_list(files, priority_display)

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

    def test_file_list_selection_defaults_to_unselected(self, priority_display):
        """Without a selection argument, no row is marked as selected."""
        files = [
            TorrentFile(
                id=0,
                name="dir/file.txt",
                size=1024,
                completed=512,
                priority=TorrentFilePriority.MEDIUM,
            ),
        ]

        result = TorrentInfoPanel.get_file_list(files, priority_display)

        assert all(item["sel"] == FileSelectionState.NONE for item in result)

    def test_file_list_selection_markers(self, priority_display):
        """Files and folders show full/partial/empty selection markers."""
        files = [
            TorrentFile(
                id=0,
                name="dir/a.txt",
                size=1024,
                completed=1024,
                priority=TorrentFilePriority.MEDIUM,
            ),
            TorrentFile(
                id=1,
                name="dir/b.txt",
                size=1024,
                completed=1024,
                priority=TorrentFilePriority.MEDIUM,
            ),
            TorrentFile(
                id=2,
                name="other/c.txt",
                size=1024,
                completed=1024,
                priority=TorrentFilePriority.MEDIUM,
            ),
        ]

        def by_file_id(result):
            return {item["id"]: item for item in result if item["is_file"]}

        def by_folder_path(result):
            return {
                item["folder_path"]: item
                for item in result
                if not item["is_file"]
            }

        # Fully select "dir" (both children), leave "other" unselected
        result = TorrentInfoPanel.get_file_list(files, priority_display, {0, 1})

        files_by_id = by_file_id(result)
        folders_by_path = by_folder_path(result)
        assert files_by_id[0]["sel"] == FileSelectionState.FULL
        assert files_by_id[1]["sel"] == FileSelectionState.FULL
        assert folders_by_path["dir"]["sel"] == FileSelectionState.FULL
        assert files_by_id[2]["sel"] == FileSelectionState.NONE
        assert folders_by_path["other"]["sel"] == FileSelectionState.NONE

        # Partially select "dir" (only one of its two children)
        result = TorrentInfoPanel.get_file_list(files, priority_display, {0})

        files_by_id = by_file_id(result)
        folders_by_path = by_folder_path(result)
        assert files_by_id[0]["sel"] == FileSelectionState.FULL
        assert files_by_id[1]["sel"] == FileSelectionState.NONE
        assert folders_by_path["dir"]["sel"] == FileSelectionState.PARTIAL


class TestFileListChildFileIds:
    """Test cases for the "child_file_ids" field of get_file_list rows."""

    def test_file_rows_have_no_children(self, priority_display):
        files = [
            TorrentFile(
                id=0,
                name="file.txt",
                size=1,
                completed=1,
                priority=TorrentFilePriority.MEDIUM,
            ),
        ]

        result = TorrentInfoPanel.get_file_list(files, priority_display)

        assert result[0]["child_file_ids"] is None

    def test_nested_folder_child_file_ids(self, priority_display):
        files = [
            TorrentFile(
                id=0,
                name="dir/sub/a.txt",
                size=1,
                completed=1,
                priority=TorrentFilePriority.MEDIUM,
            ),
            TorrentFile(
                id=1,
                name="dir/sub/b.txt",
                size=1,
                completed=1,
                priority=TorrentFilePriority.MEDIUM,
            ),
            TorrentFile(
                id=2,
                name="dir/c.txt",
                size=1,
                completed=1,
                priority=TorrentFilePriority.MEDIUM,
            ),
        ]

        result = TorrentInfoPanel.get_file_list(files, priority_display)

        folders_by_path = {
            item["folder_path"]: item for item in result if not item["is_file"]
        }
        assert set(folders_by_path["dir"]["child_file_ids"]) == {0, 1, 2}
        assert set(folders_by_path["dir/sub"]["child_file_ids"]) == {0, 1}
