# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for provider-specific details of web search results."""

import asyncio
import threading
from dataclasses import replace
from pathlib import Path

from textual.app import App

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.models import Category, DetailsSection, SearchResult
from src.tewi.ui.dialog.search.details import (
    DetailsGroupBlock,
    TorrentDetailsDialog,
    details_group,
)


def result(**kwargs) -> SearchResult:
    return SearchResult(
        title="title",
        info_hash="a" * 40,
        magnet_link=None,
        torrent_link=None,
        provider="1337x",
        provider_id="jackett",
        provider_short="1337x",
        provider_source="J",
        **kwargs,
    )


class _StubProvider(BaseSearchProvider):
    def __init__(self, error: Exception | None = None) -> None:
        super().__init__()
        self.error = error

    @property
    def id(self) -> str:
        return "jackett"

    @property
    def name(self) -> str:
        return "Jackett"

    def search(
        self,
        query: str,
        categories: list[Category] | None = None,
        indexers: list[str] | None = None,
    ) -> list[SearchResult]:
        return []

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        if self.error:
            raise self.error
        return [DetailsSection("Info", text=str(result.extra["key"]))]


def test_group_has_provider_details():
    group = details_group(_StubProvider(), result(extra={"key": "value"}))

    assert (group.title, group.source) == ("1337x", "J")
    assert group.sections == (DetailsSection("Info", text="value"),)


def test_failure_is_shown_in_group():
    group = details_group(_StubProvider(OSError("timed out")), result())

    assert group.title == "1337x"
    assert group.sections == (
        DetailsSection("Error", text="Failed to load details: timed out"),
    )


def test_missing_provider_is_shown_in_group():
    group = details_group(None, result())

    assert group.sections == (
        DetailsSection("Error", text="Provider with ID 'jackett' not found"),
    )


class _SlowProvider(_StubProvider):
    """Provider downloading details, which block until released."""

    remote_details = True

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        self.release.wait(10)
        return super().details_extended(result)


class DialogApp(App):
    CSS_PATH = str(Path(__file__).parents[5] / "src" / "tewi" / "app.tcss")

    def __init__(self, result: SearchResult, provider: BaseSearchProvider):
        super().__init__()
        self.result = result
        self.provider = provider
        self.opened: list[str] = []

    def open_url(self, url: str, *, new_tab: bool = True) -> None:
        self.opened.append(url)

    def on_mount(self) -> None:
        self.push_screen(TorrentDetailsDialog(self.result, [self.provider]))


def screen_text(app: App) -> str:
    strips = app.screen._compositor.render_strips()
    return "\n".join("".join(s.text for s in strip) for strip in strips)


def test_dialog_shows_common_details_while_loading():
    provider = _SlowProvider()
    app = DialogApp(result(extra={"key": "loaded value"}), provider)
    screens = {}

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            # Dialog is pushed after app is mounted
            await pilot.pause()
            await pilot.pause()
            screens["loading"] = screen_text(app)

            provider.release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screens["loaded"] = screen_text(app)

    asyncio.run(run())

    assert "1337x (J)" in screens["loading"]
    assert "Loading details..." in screens["loading"]
    assert "loaded value" not in screens["loading"]
    assert "Loading details..." not in screens["loaded"]
    assert "loaded value" in screens["loaded"]


def test_offline_details_are_shown_at_once():
    app = DialogApp(result(extra={"key": "local value"}), _StubProvider())
    screens = {}

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            screens["opened"] = screen_text(app)
            screens["workers"] = list(app.screen.workers)

    asyncio.run(run())

    assert "local value" in screens["opened"]
    assert "Loading details..." not in screens["opened"]
    assert screens["workers"] == []


def test_offline_group_of_remote_provider_is_none():
    assert details_group(_SlowProvider(), result(), offline=True) is None


def test_open_link_opens_first_source_page():
    first = result()
    second = replace(first, page_url="https://second.org/1")
    app = DialogApp(replace(first, sources=(first, second)), _StubProvider())

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("o")

    asyncio.run(run())

    assert app.opened == ["https://second.org/1"]


def test_links_block_is_hidden_without_pages():
    app = DialogApp(result(), _StubProvider())
    screens = {}

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            screens["opened"] = screen_text(app)

    asyncio.run(run())

    assert "─ Link ─" not in screens["opened"]
    assert "Open Link" in screens["opened"]


class _EmptySlowProvider(_SlowProvider):
    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        self.release.wait(10)
        return []


def test_group_without_loaded_details_is_removed():
    provider = _EmptySlowProvider()
    app = DialogApp(result(), provider)
    screens = {}

    async def run() -> None:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            screens["loading"] = list(app.screen.query(DetailsGroupBlock))

            provider.release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screens["loaded"] = list(app.screen.query(DetailsGroupBlock))

    asyncio.run(run())

    assert len(screens["loading"]) == 1
    assert screens["loaded"] == []
