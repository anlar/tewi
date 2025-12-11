"""Unit tests for clipboard utilities."""

from unittest.mock import patch

import src.tewi.util.clipboard as clipboard_module
from src.tewi.util.clipboard import paste


class TestPaste:
    """Tests for the paste() function."""

    def test_paste_returns_clipboard_text(self):
        """Test that paste returns text from clipboard."""
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(
                clipboard_module.pyperclip,
                "paste",
                return_value="magnet:?xt=urn:btih:test",
            ),
        ):
            result = paste()

            assert result == "magnet:?xt=urn:btih:test"

    def test_paste_returns_none_for_empty_clipboard(self):
        """Test that paste returns None when clipboard is empty."""
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(clipboard_module.pyperclip, "paste", return_value=""),
        ):
            result = paste()

            assert result is None

    def test_paste_returns_none_for_none_clipboard(self):
        """Test that paste returns None when clipboard returns None."""
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(
                clipboard_module.pyperclip, "paste", return_value=None
            ),
        ):
            result = paste()

            assert result is None

    def test_paste_handles_missing_pyperclip(self):
        """Test that paste handles missing pyperclip library gracefully."""
        with patch.object(clipboard_module, "_pyperclip_available", False):
            result = paste()

            assert result is None

    def test_paste_handles_clipboard_exception(self):
        """Test that paste handles clipboard exceptions gracefully."""
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(
                clipboard_module.pyperclip,
                "paste",
                side_effect=Exception("Clipboard error"),
            ),
        ):
            result = paste()

            assert result is None
