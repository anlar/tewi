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

"""Pytest configuration and shared fixtures."""

import pytest
from textual import _wait


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--transmission-port",
        action="store",
        default="9070",
        help="Port number for Transmission daemon (default: 9070)",
    )


@pytest.fixture(autouse=True)
def fast_pilot_pause(monkeypatch):
    """Shorten idle sleep of Textual pilot to speed up UI tests.

    Each pilot.pause() (4 per click, 1 per key press) sleeps at least
    SLEEP_GRANULARITY (20ms) after waiting for screen to process all
    pending messages, which is enough to get predictable state.
    """
    granularity = 1 / 1000
    monkeypatch.setattr(_wait, "SLEEP_GRANULARITY", granularity)
    monkeypatch.setattr(_wait, "SLEEP_IDLE", granularity / 20)
