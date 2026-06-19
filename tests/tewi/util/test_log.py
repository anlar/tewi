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

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from src.tewi.util.log import get_logger, init_logger, log_time


class TestGetLogger:
    """Test cases for get_logger function."""

    def test_returns_logger_instance(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)

    def test_returns_same_instance(self):
        """Test that get_logger returns the same instance on multiple calls."""
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2


class TestInitLogger:
    """Test cases for init_logger function."""

    @pytest.fixture(autouse=True)
    def reset_logging(self):
        """Reset logging configuration before each test."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level

        yield

        root_logger.handlers = original_handlers
        root_logger.level = original_level

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_warning_level(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger configures root logger with warning level."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        init_logger("warning")

        # Verify user_log_dir was called
        mock_user_log_dir.assert_called_once_with("tewi", appauthor=False)

        # Verify directory creation was called
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify handler was created with correct parameters
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        assert call_kwargs["encoding"] == "utf-8"

        # Verify root logger level and init message
        assert logging.getLogger().level == logging.WARNING
        mock_logger.info.assert_called_once()

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_debug_level(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger configures root logger with debug level."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("debug")

        # Verify root logger level is set to DEBUG
        assert logging.getLogger().level == logging.DEBUG

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_creates_log_file_path(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger creates correct log file path."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("info")

        # Verify the filename ends with tewi.log
        call_kwargs = mock_handler_cls.call_args[1]
        assert call_kwargs["filename"].endswith("tewi.log")

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_invalid_level(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger defaults to WARNING for invalid levels."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("invalid_level")

        # Should default to WARNING level
        assert logging.getLogger().level == logging.WARNING

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_case_insensitive(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger handles case-insensitive log levels."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("ERROR")

        # Should handle uppercase
        assert logging.getLogger().level == logging.ERROR

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_default_log_size(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger uses 10 MB maxBytes by default."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("info")

        # Verify maxBytes is set to 10 MB by default
        call_kwargs = mock_handler_cls.call_args[1]
        assert call_kwargs["maxBytes"] == 10 * 1024 * 1024

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_custom_log_size(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger converts log_size_mb to bytes correctly."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("info", log_size_mb=50)

        # Verify maxBytes is correctly converted from MB to bytes
        call_kwargs = mock_handler_cls.call_args[1]
        assert call_kwargs["maxBytes"] == 50 * 1024 * 1024

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.RotatingFileHandler")
    @patch("src.tewi.util.log.get_logger")
    def test_init_logger_backup_count(
        self,
        mock_get_logger,
        mock_handler_cls,
        mock_mkdir,
        mock_user_log_dir,
    ):
        """Test that init_logger keeps 3 backup files."""
        mock_user_log_dir.return_value = "/tmp/test_logs"
        mock_get_logger.return_value = MagicMock()

        init_logger("info")

        # Verify 3 backup files are kept
        call_kwargs = mock_handler_cls.call_args[1]
        assert call_kwargs["backupCount"] == 3


class TestLogTimeDecorator:
    """Test cases for log_time decorator."""

    def test_decorated_function_returns_value(self):
        """Test that decorated function returns its value."""

        @log_time
        def sample_function():
            return 42

        result = sample_function()
        assert result == 42

    def test_decorated_function_with_args(self):
        """Test that decorated function works with arguments."""

        @log_time
        def add(a, b):
            return a + b

        result = add(5, 3)
        assert result == 8

    def test_decorated_function_with_kwargs(self):
        """Test that decorated function works with keyword arguments."""

        @log_time
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")
        assert result == "Hi, World!"

    @patch("src.tewi.util.log.get_logger")
    def test_logs_when_execution_exceeds_threshold(self, mock_get_logger):
        """Test that log_time logs when execution time exceeds 1ms."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        @log_time
        def slow_function():
            time.sleep(0.002)  # Sleep for 2ms
            return "done"

        result = slow_function()

        assert result == "done"
        # Verify logger.debug was called
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "slow_function" in call_args
        assert "ms" in call_args

    @patch("src.tewi.util.log.get_logger")
    def test_does_not_log_when_execution_below_threshold(self, mock_get_logger):
        """Test that log_time doesn't log when execution time is below 1ms."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        @log_time
        def fast_function():
            return "done"

        result = fast_function()

        assert result == "done"
        # Verify logger.debug was not called (execution < 1ms)
        mock_logger.debug.assert_not_called()

    def test_preserves_function_name(self):
        """Test that decorator preserves function name."""

        @log_time
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_preserves_function_docstring(self):
        """Test that decorator preserves function docstring."""

        @log_time
        def documented_function():
            """This is a docstring."""
            pass

        assert documented_function.__doc__ == "This is a docstring."

    @patch("src.tewi.util.log.get_logger")
    def test_handles_exceptions(self, mock_get_logger):
        """Test that decorator allows exceptions to propagate."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        @log_time
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Logger should not be called when exception occurs
        mock_logger.debug.assert_not_called()

    @patch("src.tewi.util.log.get_logger")
    def test_logs_qualified_name(self, mock_get_logger):
        """Test that log_time uses qualified function name."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        class MyClass:
            @log_time
            def method(self):
                time.sleep(0.002)
                return "result"

        obj = MyClass()
        obj.method()

        # Verify qualified name is used
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[0][0]
        assert "MyClass.method" in call_args or "method" in call_args
