"""Unit tests for clipboard utilities."""

from unittest.mock import patch

import pytest

import src.tewi.util.clipboard as clipboard_module
from src.tewi.util.clipboard import (
    copy,
    is_available,
    is_remote_session,
    paste,
)

SSH_VARS = ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")


@pytest.fixture(autouse=True)
def local_session(monkeypatch):
    """Run tests as in local session, even if test runs over SSH."""
    for var in SSH_VARS:
        monkeypatch.delenv(var, raising=False)


class TestRemoteSession:
    """Tests for detecting SSH session, where clipboard is not user's."""

    def test_local_session(self):
        assert is_remote_session() is False

    @pytest.mark.parametrize("var", SSH_VARS)
    def test_ssh_session(self, monkeypatch, var):
        monkeypatch.setenv(var, "10.0.0.1 5000 10.0.0.2 22")
        assert is_remote_session() is True

    def test_clipboard_unavailable_in_ssh_session(self, monkeypatch):
        monkeypatch.setenv("SSH_CONNECTION", "10.0.0.1 5000 10.0.0.2 22")
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(clipboard_module.pyperclip, "copy") as mock_copy,
            patch.object(clipboard_module.pyperclip, "paste") as mock_paste,
        ):
            assert is_available() is False
            assert copy("text") is False
            assert paste() is None
            mock_copy.assert_not_called()
            mock_paste.assert_not_called()


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


class TestCopy:
    """Tests for the copy() function."""

    def test_copy_puts_text_to_clipboard(self):
        """Test that copy passes text to clipboard."""
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(clipboard_module.pyperclip, "copy") as mock_copy,
        ):
            assert copy("magnet:?xt=urn:btih:test") is True
            mock_copy.assert_called_once_with("magnet:?xt=urn:btih:test")

    def test_copy_handles_missing_pyperclip(self):
        """Test that copy reports failure without pyperclip library."""
        with patch.object(clipboard_module, "_pyperclip_available", False):
            assert copy("text") is False

    def test_copy_handles_clipboard_exception(self):
        """Test that copy reports failure when clipboard access fails."""
        with (
            patch.object(clipboard_module, "_pyperclip_available", True),
            patch.object(
                clipboard_module.pyperclip,
                "copy",
                side_effect=Exception("Clipboard error"),
            ),
        ):
            assert copy("text") is False
