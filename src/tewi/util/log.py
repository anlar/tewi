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

import logging
import re
import textwrap
import time
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar

from platformdirs import user_log_dir

P = ParamSpec("P")
T = TypeVar("T")

_BACKUP_COUNT = 3

# Control characters except tab (line breaks included)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")
_ESCAPES = {"\n": "\\n", "\r": "\\r"}


class _EscapingFormatter(logging.Formatter):
    """Formatter escaping line breaks and control characters in messages.

    Messages may contain text from torrent clients and search providers
    (e.g. error messages), which could otherwise forge log entries.
    Tracebacks keep their line breaks, but are indented, so text from
    exception messages can't look like separate log entries.
    """

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802
        record.message = _CONTROL_CHARS_RE.sub(
            lambda m: _ESCAPES.get(m[0], f"\\x{ord(m[0]):02x}"),
            record.message,
        )
        return super().formatMessage(record)

    def formatException(self, ei) -> str:  # noqa: N802
        return textwrap.indent(super().formatException(ei), "  ")


def get_logger() -> logging.Logger:
    """Get the Tewi logger instance.

    Returns:
        Logger instance for Tewi application
    """
    return logging.getLogger("tewi")


def init_logger(log_level: str, log_size_mb: int = 10) -> None:
    """Initialize logging configuration with size-based rotation.

    Args:
        log_level: Log level (debug, info, warning, error, critical)
        log_size_mb: Max size in MB per log file (default: 10).
                     Up to 3 backup files are kept, so total disk
                     usage is at most log_size_mb * 4 MB.
    """
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    level = level_map.get(log_level.lower(), logging.WARNING)

    # Logs may contain sensitive data, so directory is accessible only by
    # owner
    log_dir = Path(user_log_dir("tewi", appauthor=False))
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    log_file = log_dir / "tewi.log"

    handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=log_size_mb * 1024 * 1024,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        _EscapingFormatter(
            fmt=(
                "%(asctime)s.%(msecs)03d"
                " %(module)-15s %(levelname)-8s %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    logger = get_logger()
    logger.info(
        f"Logging initialized: level={log_level.upper()},"
        f" file={log_file}, log_size_mb={log_size_mb}"
    )


def log_time(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to log function execution time if it exceeds 1ms."""

    @wraps(func)
    def log_time_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start_time = time.perf_counter()

        result = func(*args, **kwargs)

        end_time = time.perf_counter()

        total_time_ms = (end_time - start_time) * 1000

        if total_time_ms > 1:
            logger = get_logger()
            logger.debug(
                f'Function "{func.__qualname__}": {total_time_ms:.4f} ms'
            )

        return result

    return log_time_wrapper
