#!/usr/bin/env python3

# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2024  Anton Larionov
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

from src.tewi.ui.util import subtitle_keys


class TestSubtitleKeys:
    """Test cases for subtitle_keys function."""

    def test_single_key(self):
        """Test formatting a single key-description pair."""
        result = subtitle_keys(("X", "Close"))
        assert result == "<X> [dim]Close[/]"

    def test_two_keys(self):
        """Test formatting two key-description pairs."""
        result = subtitle_keys(("Y", "Yes"), ("N", "No"))
        expected = "<Y> [dim]Yes[/] [dim]·[/] <N> [dim]No[/]"
        assert result == expected

    def test_multiple_keys(self):
        """Test formatting multiple key-description pairs."""
        result = subtitle_keys(
            ("A", "Add"),
            ("O", "Open Link"),
            ("Enter", "Details"),
            ("X", "Close"),
        )
        expected = (
            "<A> [dim]Add[/] [dim]·[/] "
            "<O> [dim]Open Link[/] [dim]·[/] "
            "<Enter> [dim]Details[/] [dim]·[/] "
            "<X> [dim]Close[/]"
        )
        assert result == expected

    def test_word_keys(self):
        """Test formatting with word keys like Enter, Tab, ESC."""
        result = subtitle_keys(
            ("Enter", "Search"), ("Tab", "Switch"), ("ESC", "Close")
        )
        expected = (
            "<Enter> [dim]Search[/] [dim]·[/] "
            "<Tab> [dim]Switch[/] [dim]·[/] "
            "<ESC> [dim]Close[/]"
        )
        assert result == expected

    def test_mixed_key_types(self):
        """Test formatting with mixed single-letter and word keys."""
        result = subtitle_keys(
            ("Enter", "Update"), ("Tab", "Switch field"), ("ESC", "Close")
        )
        expected = (
            "<Enter> [dim]Update[/] [dim]·[/] "
            "<Tab> [dim]Switch field[/] [dim]·[/] "
            "<ESC> [dim]Close[/]"
        )
        assert result == expected

    def test_empty_input(self):
        """Test formatting with no keys."""
        result = subtitle_keys()
        assert result == ""

    def test_numeric_keys(self):
        """Test formatting with numeric keys."""
        result = subtitle_keys(
            ("1/O", "Overview"), ("2/F", "Files"), ("3/P", "Peers")
        )
        expected = (
            "<1/O> [dim]Overview[/] [dim]·[/] "
            "<2/F> [dim]Files[/] [dim]·[/] "
            "<3/P> [dim]Peers[/]"
        )
        assert result == expected
