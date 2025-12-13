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
        # Store original handlers
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level

        yield

        # Restore original handlers
        root_logger.handlers = original_handlers
        root_logger.level = original_level

    def test_init_logger_disabled(self):
        """Test that init_logger does nothing when enable_logs is False."""
        # Get handler count before
        root_logger = logging.getLogger()
        handler_count_before = len(root_logger.handlers)

        init_logger(False)

        # Handler count should not change
        handler_count_after = len(root_logger.handlers)
        assert handler_count_after == handler_count_before

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.logging.basicConfig")
    def test_init_logger_enabled(
        self, mock_basic_config, mock_mkdir, mock_user_log_dir
    ):
        """Test that init_logger configures logging when enable_logs is True."""
        # Setup mocks
        mock_user_log_dir.return_value = "/tmp/test_logs"

        init_logger(True)

        # Verify user_log_dir was called
        mock_user_log_dir.assert_called_once_with("tewi", appauthor=False)

        # Verify directory creation was called
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify logging.basicConfig was called
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]

        # Check that basicConfig was called with correct parameters
        assert "filename" in call_kwargs
        assert call_kwargs["encoding"] == "utf-8"
        assert call_kwargs["level"] == logging.DEBUG
        assert "format" in call_kwargs
        assert "datefmt" in call_kwargs

    @patch("src.tewi.util.log.user_log_dir")
    @patch("src.tewi.util.log.Path.mkdir")
    @patch("src.tewi.util.log.logging.basicConfig")
    def test_init_logger_creates_log_file_path(
        self, mock_basic_config, mock_mkdir, mock_user_log_dir
    ):
        """Test that init_logger creates correct log file path."""
        mock_user_log_dir.return_value = "/tmp/test_logs"

        init_logger(True)

        # Verify the filename ends with tewi.log
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs["filename"].endswith("tewi.log")


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
