# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for status line below torrent list."""

import asyncio

import pytest
from textual.app import App, ComposeResult

from src.tewi.ui.models import MarkState
from src.tewi.ui.panel.state import StatePanel


class StateApp(App):
    def compose(self) -> ComposeResult:
        yield StatePanel()


@pytest.mark.parametrize(
    "marks,expected",
    [
        (None, ""),
        # Posted by torrent list on first update, before anything is marked
        (MarkState(listed=0, hidden=0), ""),
        (MarkState(listed=2, hidden=0), "Marked: 2"),
        (MarkState(listed=0, hidden=3), "Marked: 3 hidden"),
        (MarkState(listed=2, hidden=3), "Marked: 2 (+3 hidden)"),
    ],
)
def test_marked_torrents_count(marks, expected):
    async def run() -> None:
        app = StateApp()
        async with app.run_test() as pilot:
            panel = app.query_one(StatePanel)
            panel.r_marks = MarkState(listed=1, hidden=0)
            panel.r_marks = marks
            await pilot.pause()

            assert panel.r_marked == expected
            assert panel.has_class("marked-none") == (expected == "")

    asyncio.run(run())


GB = 1024**3


@pytest.mark.parametrize(
    "complete,total,expected",
    [
        # Formatted sizes compare wrong as strings ("5.37 GB" > "10.74 GB")
        (5 * GB, 10 * GB, "Size: 5.37 GB / 10.74 GB"),
        (900 * 1024**2, 1.2 * GB, "Size: 943.72 MB / 1.29 GB"),
        (10 * GB, 10 * GB, "Size: 10.74 GB"),
    ],
)
def test_stats_size_shows_total_while_incomplete(complete, total, expected):
    session = {
        "torrents_count": 1,
        "torrents_check": 0,
        "torrents_down": 0,
        "torrents_seed": 0,
        "torrents_stop": 0,
        "torrents_complete_size": complete,
        "torrents_total_size": total,
    }

    assert StatePanel().print_stats(session).endswith(expected)
