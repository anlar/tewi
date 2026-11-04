# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2026  Anton Larionov
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

"""Regression tests for Rich markup injection from remote data.

Text from torrents, peers, trackers and search providers must never be
parsed as markup: "[@click=...]" markup runs Textual action on mouse
click, e.g. app.screenshot() which can overwrite arbitrary file.
"""

import asyncio
from types import SimpleNamespace

import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from src.tewi.app import MainApp
from src.tewi.search.models import SearchResult
from src.tewi.ui.panel.details import _style_cell
from src.tewi.ui.panel.websearch import TorrentWebSearch
from src.tewi.ui.util import plain_text
from src.tewi.ui.widget.common import ReactiveLabel

PAYLOADS = [
    "[@click=app.pwn()]uTorrent 3.6[/]",
    # Backslash turned old escaping ("[" -> "\[") into literal backslash
    # followed by a real tag
    r"\[@click=app.pwn()]uTorrent 3.6[/]",
    "[link=file:///etc/passwd]uTorrent 3.6[/link]",
]


def has_markup_style(text: Text) -> bool:
    """Check if text got any style from markup (actions, links, etc)."""
    return any(
        "@click" in str(span.style) or "link" in str(span.style)
        for span in text.spans
    )


class TestPlainText:
    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_payload_is_not_parsed(self, payload):
        text = plain_text(payload)

        assert text.plain == payload
        assert not has_markup_style(text)

    def test_none_is_empty(self):
        assert plain_text(None).plain == ""

    def test_style_and_justify(self):
        text = plain_text("name", "bold", justify="right")

        assert text.style == "bold"
        assert text.justify == "right"


class TestStyleCell:
    @pytest.mark.parametrize("payload", PAYLOADS)
    @pytest.mark.parametrize("style", ["", "bold dim"])
    def test_file_name_is_not_parsed(self, payload, style):
        text = _style_cell(payload, style)

        assert text.plain == payload
        assert not has_markup_style(text)

    def test_trusted_markup_is_parsed(self):
        text = _style_cell("[bold red]↑[/]", "dim", markup=True)

        assert text.plain == "↑"
        assert text.style == "dim"
        assert text.spans

    def test_none_is_empty(self):
        assert _style_cell(None, "bold").plain == ""


class ClickApp(App):
    """App recording calls of action injected via markup."""

    def __init__(self) -> None:
        super().__init__()
        self.pwned = 0

    def action_pwn(self) -> None:
        self.pwned += 1


class TableApp(ClickApp):
    def __init__(self, cell) -> None:
        super().__init__()
        self.cell = cell

    def compose(self) -> ComposeResult:
        yield DataTable()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Client")
        table.add_row(self.cell)


async def click_first_row(pilot, table: DataTable) -> None:
    await pilot.pause()
    for x in range(1, 12):
        await pilot.click(table, offset=(x, 1))
    await pilot.pause()


def test_table_cell_markup_runs_action_on_click():
    """Ensure test setup reproduces the attack with plain str cell."""

    async def run() -> None:
        app = TableApp(PAYLOADS[0])
        async with app.run_test() as pilot:
            await click_first_row(pilot, app.query_one(DataTable))
            assert app.pwned > 0

    asyncio.run(run())


@pytest.mark.parametrize("payload", PAYLOADS)
def test_plain_text_cell_does_not_run_action_on_click(payload):
    async def run() -> None:
        app = TableApp(plain_text(payload))
        async with app.run_test() as pilot:
            await click_first_row(pilot, app.query_one(DataTable))
            assert app.pwned == 0

    asyncio.run(run())


class LabelApp(ClickApp):
    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value

    def compose(self) -> ComposeResult:
        yield ReactiveLabel()

    def on_mount(self) -> None:
        self.query_one(ReactiveLabel).name = self.value


@pytest.mark.parametrize("payload", PAYLOADS)
def test_reactive_label_does_not_parse_markup_by_default(payload):
    async def run() -> None:
        app = LabelApp(payload)
        async with app.run_test(size=(120, 10)) as pilot:
            await pilot.pause()
            label = app.query_one(ReactiveLabel)
            line = "".join(s.text for s in label.render_line(0))
            assert line.rstrip() == payload

            for x in range(1, 30, 2):
                await pilot.click(ReactiveLabel, offset=(x, 0))
            await pilot.pause()
            assert app.pwned == 0

    asyncio.run(run())


class WebSearchApp(ClickApp):
    def __init__(self) -> None:
        super().__init__()
        self.search = SimpleNamespace(get_providers=lambda: [])

    def compose(self) -> ComposeResult:
        yield TorrentWebSearch(False, "standard")


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("freeleech", [False, True])
def test_web_search_title_does_not_run_action_on_click(payload, freeleech):
    async def run() -> None:
        app = WebSearchApp()
        async with app.run_test(size=(160, 40)) as pilot:
            panel = app.query_one(TorrentWebSearch)
            panel.r_results = [
                SearchResult(
                    title=payload,
                    info_hash="a" * 40,
                    magnet_link=None,
                    torrent_link=None,
                    provider=payload,
                    provider_id="test",
                    provider_short=payload,
                    seeders=1,
                    size=1,
                    freeleech=freeleech,
                )
            ]
            await pilot.pause()

            table = panel.query_one(DataTable)
            row = table.get_row_at(0)
            title = row[-1]
            assert title.plain.endswith(payload)
            assert not has_markup_style(title)
            assert not has_markup_style(row[0])

            for x in range(1, table.size.width, 4):
                await pilot.click(table, offset=(x, 1))
            await pilot.pause()
            assert app.pwned == 0

    asyncio.run(run())


class TestCheckActionBlocksUnsafeActions:
    @pytest.fixture
    def app(self):
        return SimpleNamespace(client=None)

    def test_screenshot_binding_is_allowed(self, app):
        assert MainApp.check_action(app, "screenshot", ()) is True

    def test_screenshot_with_parameters_is_blocked(self, app):
        params = ("../.bashrc", ".")
        assert MainApp.check_action(app, "screenshot", params) is False

    @pytest.mark.parametrize("action", ["simulate_key", "suspend_process"])
    def test_unused_unsafe_actions_are_blocked(self, app, action):
        assert MainApp.check_action(app, action, ()) is False
        assert MainApp.check_action(app, action, ("q",)) is False

    def test_regular_action_is_allowed(self, app):
        assert MainApp.check_action(app, "help", ()) is True
