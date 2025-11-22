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
from src.tewi.common import FilePriority
from src.tewi.util.data import print_priority


class TestPrintPriority:
    """Test cases for print_priority function."""

    @pytest.mark.parametrize("priority", list(FilePriority))
    def test_returns_non_empty_string(self, priority):
        """Test that all priorities return non-empty string values."""
        result = print_priority(priority)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unique_outputs(self):
        """Test that each priority level has a unique output."""
        results = [print_priority(p) for p in list(FilePriority)]
        assert len(results) == len(set(results))

    @pytest.mark.parametrize("priority", list(FilePriority))
    def test_rich_text_parseable(self, priority):
        """Test that outputs can be parsed by Rich Text."""
        result = print_priority(priority)
        # Should not raise an exception
        text = Text.from_markup(result)
        assert text is not None
