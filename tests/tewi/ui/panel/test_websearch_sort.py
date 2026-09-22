import asyncio
from datetime import datetime
from types import SimpleNamespace

from textual import on
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from src.tewi.search.models import SearchResult
from src.tewi.ui.dialog.search.sort import SearchSortDialog
from src.tewi.ui.messages import AddTorrentFromWebSearchCommand
from src.tewi.ui.panel.websearch import TorrentWebSearch


def result(title: str, seeders: int, size: int) -> SearchResult:
    return SearchResult(
        title=title,
        info_hash=title,
        magnet_link=f"magnet:?xt=urn:btih:{title}",
        torrent_link=None,
        provider="Test",
        provider_id="test",
        provider_short="T",
        seeders=seeders,
        size=size,
        upload_date=datetime(2026, 1, 1),
    )


class WebSearchApp(App):
    def __init__(self, *, hide_zero_seeders: bool = False) -> None:
        super().__init__()
        self.search = SimpleNamespace(get_providers=lambda: [])
        self.hide_zero_seeders = hide_zero_seeders
        self.added: list[str] = []

    def compose(self) -> ComposeResult:
        yield TorrentWebSearch(self.hide_zero_seeders, "standard")

    @on(AddTorrentFromWebSearchCommand)
    def handle_added(self, event: AddTorrentFromWebSearchCommand) -> None:
        self.added.append(event.magnet_link)


def test_sort_dialog_reorders_rows_without_changing_selected_torrent():
    async def run() -> None:
        app = WebSearchApp()
        async with app.run_test(size=(120, 40)) as pilot:
            panel = app.query_one(TorrentWebSearch)
            panel.r_results = [
                result("Alpha", 10, 1),
                result("Zulu", 1, 3),
                result("Mike", 5, 2),
            ]
            await pilot.pause()

            table = panel.query_one(DataTable)
            assert [r.title for r in panel._display_results] == [
                "Alpha",
                "Mike",
                "Zulu",
            ]
            table.move_cursor(row=2)
            assert panel.selected_result().title == "Zulu"

            await pilot.press("s")
            assert isinstance(app.screen, SearchSortDialog)
            assert app.screen.query_one(DataTable).row_count == 9
            await pilot.press("Z")  # Size, largest first.
            await pilot.pause()

            assert app.screen is app._screen_stack[0]
            assert [r.title for r in panel._display_results] == [
                "Zulu",
                "Mike",
                "Alpha",
            ]
            assert table.cursor_row == 0
            assert panel.selected_result().title == "Zulu"
            assert "Sort: Size ↓" in panel.r_search_status

            panel.action_add_torrent()
            await pilot.pause()
            assert app.added == ["magnet:?xt=urn:btih:Zulu"]

            await pilot.press("s", "n")  # Name, A to Z.
            assert [r.title for r in panel._display_results] == [
                "Alpha",
                "Mike",
                "Zulu",
            ]
            assert table.cursor_row == 2
            assert panel.selected_result().title == "Zulu"
            assert "Sort: Name ↑" in panel.r_search_status

            await pilot.press("v")
            assert panel._view_compact
            assert "Sort: Name ↑" in panel.r_search_status

    asyncio.run(run())


def test_hidden_zero_seeder_result_does_not_change_selected_action():
    async def run() -> None:
        app = WebSearchApp(hide_zero_seeders=True)
        async with app.run_test(size=(120, 40)) as pilot:
            panel = app.query_one(TorrentWebSearch)
            panel.r_results = [
                result("hidden", 0, 1),
                result("visible", 5, 2),
            ]
            await pilot.pause()

            assert [r.title for r in panel._display_results] == ["visible"]
            panel.action_add_torrent()
            await pilot.pause()
            assert app.added == ["magnet:?xt=urn:btih:visible"]

    asyncio.run(run())
