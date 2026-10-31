import asyncio
from pathlib import Path
from types import SimpleNamespace

from textual import on
from textual.app import App
from textual.widgets import DataTable

from src.tewi.ui.dialog.torrent.sort import SortOrderDialog, SortOrderWidget
from src.tewi.ui.messages import SortOrderUpdatedEvent
from src.tewi.ui.models import (
    SortKey,
    default_sort_keys,
    sort_orders,
    sort_torrents,
)
from src.tewi.ui.panel.state import StatePanel


def order(order_id: str):
    return next(o for o in sort_orders if o.id == order_id)


def torrent(name: str, percent_done: float, added_date: int):
    return SimpleNamespace(
        name=name, percent_done=percent_done, added_date=added_date
    )


def test_sort_torrents_breaks_ties_with_following_keys():
    torrents = [
        torrent("a", 0.5, 3),
        torrent("b", 1.0, 1),
        torrent("c", 0.5, 1),
        torrent("d", 1.0, 2),
    ]

    sort_torrents(
        torrents,
        (SortKey(order("progress"), False), SortKey(order("age"), True)),
    )

    assert [t.name for t in torrents] == ["b", "d", "c", "a"]


def test_sort_torrents_single_key():
    torrents = [torrent("b", 0, 0), torrent("a", 0, 0), torrent("c", 0, 0)]

    sort_torrents(torrents, (SortKey(order("name"), False),))

    assert [t.name for t in torrents] == ["c", "b", "a"]


def test_status_shows_primary_order_and_count_of_following():
    panel = StatePanel()

    panel.update_sort((SortKey(order("age"), True),))
    assert panel.r_sort == "Sort: Age"

    panel.update_sort(
        (
            SortKey(order("progress"), False),
            SortKey(order("age"), True),
            SortKey(order("name"), False),
        )
    )
    assert panel.r_sort == "Sort: Progress ↑ +2"


class SortApp(App):
    # app styles define dialog size
    CSS_PATH = str(Path(__file__).parents[3] / "src" / "tewi" / "app.tcss")

    def __init__(self, sort_keys: tuple[SortKey, ...]) -> None:
        super().__init__()
        self.sort_keys = sort_keys
        self.events: list[SortOrderUpdatedEvent] = []

    def on_mount(self) -> None:
        self.push_screen(SortOrderDialog(self.sort_keys))

    @on(SortOrderUpdatedEvent)
    def handle_sort(self, event: SortOrderUpdatedEvent) -> None:
        self.events.append(event)


def is_multi(app: App) -> bool:
    table = app.screen.query_one(DataTable)
    first = next(iter(table.columns.values()))
    # order names are indented to make room for position prefix
    return str(first.label).startswith(" ")


def layout(app: App) -> tuple[int, ...]:
    """Dialog width followed by widths of table columns."""
    table = app.screen.query_one(DataTable)
    return (
        app.screen.query_one(SortOrderWidget).size.width,
        *(c.get_render_width(table) for c in table.columns.values()),
    )


def order_cell(app: App, order_id: str) -> str:
    table = app.screen.query_one(DataTable)
    row = next(i for i, o in enumerate(sort_orders) if o.id == order_id)
    return str(table.get_row_at(row)[0])


def test_single_mode_applies_order_and_closes():
    async def run() -> None:
        app = SortApp((SortKey(order("age"), True),))
        async with app.run_test() as pilot:
            assert not is_multi(app)

            await pilot.press("P")

            assert app.events[-1].sort_keys == (
                SortKey(order("progress"), False),
            )
            assert app.events[-1].notify
            assert not isinstance(app.screen, SortOrderDialog)

    asyncio.run(run())


def test_multi_mode_builds_chain_of_sort_keys():
    async def run() -> None:
        app = SortApp((SortKey(order("age"), True),))
        async with app.run_test() as pilot:
            single_layout = layout(app)
            assert order_cell(app, "age") == "Age"

            await pilot.press("m")
            assert is_multi(app)
            assert order_cell(app, "age") == "   Age"
            # toggling mode only shifts order names, dialog and columns
            # keep their size
            assert layout(app) == single_layout

            await pilot.press("m")
            assert not is_multi(app)
            assert layout(app) == single_layout

            await pilot.press("m")

            await pilot.press("P", "a")

            assert isinstance(app.screen, SortOrderDialog)
            assert app.events[-1].sort_keys == (
                SortKey(order("progress"), False),
                SortKey(order("age"), True),
            )
            assert not app.events[-1].notify
            assert order_cell(app, "progress") == "1↑ Progress"
            assert order_cell(app, "age") == "2  Age"
            assert layout(app) == single_layout

            # opposite direction flips key in place
            await pilot.press("p")
            assert order_cell(app, "progress") == "1  Progress"

            # same key again removes it from chain
            await pilot.press("p")
            assert app.events[-1].sort_keys == (SortKey(order("age"), True),)
            assert order_cell(app, "progress") == "   Progress"
            assert order_cell(app, "age") == "1  Age"

    asyncio.run(run())


def test_multi_mode_toggle_off_resets_to_single_mode():
    async def run() -> None:
        keys = (
            SortKey(order("progress"), False),
            SortKey(order("age"), True),
        )
        app = SortApp(keys)
        async with app.run_test() as pilot:
            # existing chain reopens in multi mode
            assert is_multi(app)
            assert order_cell(app, "age") == "2  Age"

            await pilot.press("m")
            assert not is_multi(app)
            assert app.events == []

            await pilot.press("n")
            assert app.events[-1].sort_keys == (SortKey(order("name"), True),)
            assert not isinstance(app.screen, SortOrderDialog)

    asyncio.run(run())


def test_multi_mode_emptied_chain_falls_back_to_default_sort():
    async def run() -> None:
        app = SortApp((SortKey(order("age"), True),))
        async with app.run_test() as pilot:
            await pilot.press("m", "N", "N")

            assert app.events[-1].sort_keys == default_sort_keys
            assert not app.events[-1].notify
            assert order_cell(app, "name") == "   Name"
            assert order_cell(app, "age") == "   Age"

            # next selected order starts new chain instead of default one
            await pilot.press("z")
            assert app.events[-1].sort_keys == (SortKey(order("size"), True),)
            assert order_cell(app, "size") == "1  Size"

    asyncio.run(run())
