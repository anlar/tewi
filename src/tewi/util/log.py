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
import time
from functools import wraps
from pathlib import Path

from platformdirs import user_log_dir


def get_logger() -> logging.Logger:
    """Get the Tewi logger instance.

    Returns:
        Logger instance for Tewi application
    """
    return logging.getLogger("tewi")


def init_logger(log_level: str) -> None:
    """Initialize logging configuration.

    Args:
        log_level: Log level (debug, info, warning, error, critical)
    """
    # Map string levels to logging constants
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    level = level_map.get(log_level.lower(), logging.WARNING)

    # Always set up file logging
    log_dir = Path(user_log_dir("tewi", appauthor=False))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tewi.log"
    logging.basicConfig(
        filename=str(log_file),
        encoding="utf-8",
        format="%(asctime)s.%(msecs)03d %(module)-15s "
        "%(levelname)-8s %(message)s",
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Log initialization info
    logger = get_logger()
    logger.info(
        f"Logging initialized: level={log_level.upper()}, file={log_file}"
    )


def log_time(func):
    """Decorator to log function execution time if it exceeds 1ms."""

    @wraps(func)
    def log_time_wrapper(*args, **kwargs):
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
