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
