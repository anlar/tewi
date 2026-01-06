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

from .log import get_logger

logger = get_logger()


def start_debugpy(port: int) -> None:
    """
    Start debugpy server on the specified port.

    If debugpy is not available as a dependency, logs a warning instead.

    Args:
        port: Port number to listen on for debugger connections
    """
    try:
        import debugpy

        _ = debugpy.listen(port)
        logger.info(f"debugpy server started on port {port}")
    except ImportError:
        logger.warning("debugpy is not available - cannot start debug server")
