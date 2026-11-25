# SPDX-FileCopyrightText: 2024 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

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
