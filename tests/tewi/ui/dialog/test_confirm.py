# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for confirmation dialog."""

import asyncio

from textual.app import App
from textual.widgets import Label

from src.tewi.ui.dialog.confirm import TEXT_WIDTH, ConfirmDialog


class ConfirmApp(App):
    CSS_PATH = "../../../../src/tewi/app.tcss"

    def __init__(self, items: list[str]) -> None:
        super().__init__()
        self.items = items

    def on_mount(self) -> None:
        self.push_screen(ConfirmDialog("Remove?", "Description", self.items))


def test_items_are_single_lines_shown_literally():
    """Items are torrent names: long ones are cut, markup isn't parsed."""
    long_name = "x" * 100
    wide_name = "漢" * 40

    async def run() -> None:
        app = ConfirmApp([long_name, wide_name, "[b]bold[/b]"])
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            labels = list(app.screen.query(Label))[-3:]
            lines = [
                "".join(s.text for s in label.render_line(0)).rstrip()
                for label in labels
            ]

            assert [label.size.height for label in labels] == [1, 1, 1]
            assert lines[0] == "• " + "x" * (TEXT_WIDTH - 3) + "…"
            assert lines[1].endswith("…")
            assert lines[2] == "• [b]bold[/b]"

    asyncio.run(run())
