"""Tests for marking torrents in torrent list to run actions on them."""

import asyncio

import pytest
from textual import on
from textual.app import App, ComposeResult

from src.tewi.torrent.models import Torrent
from src.tewi.ui.messages import (
    ClearFiltersCommand,
    MarksChangedEvent,
    RemoveTorrentCommand,
    TorrentRemovedEvent,
    VerifyTorrentCommand,
)
from src.tewi.ui.models import MarkState
from src.tewi.ui.panel.listview import MARK, TorrentListViewPanel
from tests.tewi.ui.helpers import make_list_panel, make_torrent

TORRENTS = [make_torrent(name) for name in ("a", "b", "c", "d")]


class ListApp(App):
    def __init__(self, page_size: int = 100) -> None:
        super().__init__()
        self.page_size = page_size
        self.messages = []

    def compose(self) -> ComposeResult:
        yield make_list_panel(self.page_size)

    def on_mount(self) -> None:
        self.panel.focus()

    @property
    def panel(self) -> TorrentListViewPanel:
        return self.query_one(TorrentListViewPanel)

    @property
    def mark_states(self) -> list[MarkState]:
        return [
            m.state for m in self.messages if isinstance(m, MarksChangedEvent)
        ]

    def commands(self, kind: type) -> list:
        return [m for m in self.messages if isinstance(m, kind)]

    @on(MarksChangedEvent)
    @on(ClearFiltersCommand)
    @on(RemoveTorrentCommand)
    @on(VerifyTorrentCommand)
    def record(self, message) -> None:
        self.messages.append(message)


def run_list(test, torrents=TORRENTS, page_size: int = 100) -> None:
    async def run() -> None:
        app = ListApp(page_size)
        async with app.run_test(size=(100, 20)) as pilot:
            app.panel.r_torrents = list(torrents)
            await pilot.pause()
            await test(app, pilot)

    asyncio.run(run())


def names(torrents: list[Torrent]) -> list[str]:
    return [t.name for t in torrents]


def test_space_marks_and_moves_to_next_torrent():
    async def test(app, pilot):
        await pilot.press("space", "space")

        assert app.panel.marked == {"hash-a", "hash-b"}
        assert app.panel.get_hl_torrent().name == "c"
        assert app.mark_states[-1] == MarkState(listed=2, hidden=0)

        # Second press on marked torrent unmarks it
        await pilot.press("k", "space")
        assert app.panel.marked == {"hash-a"}

    run_list(test)


def test_space_on_last_torrent_stays_on_it():
    async def test(app, pilot):
        await pilot.press("G", "space")

        assert app.panel.marked == {"hash-d"}
        assert app.panel.get_hl_torrent().name == "d"

    run_list(test)


def test_space_moves_to_next_page():
    async def test(app, pilot):
        await pilot.press("space", "space")

        assert app.panel.marked == {"hash-a", "hash-b"}
        assert app.panel.page_state.current == 1
        assert app.panel.get_hl_torrent().name == "c"

    run_list(test, page_size=2)


def test_actions_use_highlighted_torrent_without_marks():
    async def test(app, pilot):
        await pilot.press("j", "v")

        assert [
            c.torrent_hashes for c in app.commands(VerifyTorrentCommand)
        ] == [["hash-b"]]

    run_list(test)


def test_actions_use_only_marked_torrents_in_list_order():
    async def test(app, pilot):
        # Mark d, then a; cursor ends on b, which isn't marked
        await pilot.press("G", "space", "g", "space", "v")

        assert app.panel.get_hl_torrent().name == "b"
        assert [
            c.torrent_hashes for c in app.commands(VerifyTorrentCommand)
        ] == [["hash-a", "hash-d"]]

    run_list(test)


def test_mark_all_marks_all_pages_and_clears():
    async def test(app, pilot):
        await pilot.press("V")
        assert names(app.panel.marked_torrents()) == ["a", "b", "c", "d"]

        await pilot.press("V")
        assert app.panel.marked == set()
        assert app.mark_states[-1] == MarkState(listed=0, hidden=0)

    run_list(test, page_size=2)


def test_escape_clears_marks_before_filters():
    async def test(app, pilot):
        await pilot.press("space", "escape")

        assert app.panel.marked == set()
        assert app.commands(ClearFiltersCommand) == []

        await pilot.press("escape")
        assert len(app.commands(ClearFiltersCommand)) == 1

    run_list(test)


def test_marks_of_hidden_torrents_are_kept_but_not_used():
    async def test(app, pilot):
        await pilot.press("space", "space")

        # Filter hides torrent a
        app.panel.r_torrents = TORRENTS[1:]
        await pilot.pause()

        assert app.mark_states[-1] == MarkState(listed=1, hidden=1)
        assert names(app.panel.target_torrents()) == ["b"]

        # Only hidden torrents are marked: cursor torrent is used, and
        # Esc clears filters, not invisible marks
        app.panel.r_torrents = TORRENTS[2:]
        await pilot.pause()

        assert app.mark_states[-1] == MarkState(listed=0, hidden=2)
        assert names(app.panel.target_torrents()) == ["c"]

        await pilot.press("escape")
        assert app.panel.marked == {"hash-a", "hash-b"}
        assert len(app.commands(ClearFiltersCommand)) == 1

        # Torrents shown again are still marked
        app.panel.r_torrents = list(TORRENTS)
        await pilot.pause()

        assert names(app.panel.target_torrents()) == ["a", "b"]
        assert app.mark_states[-1] == MarkState(listed=2, hidden=0)

    run_list(test)


def test_marks_of_torrents_missing_in_client_are_dropped():
    async def test(app, pilot):
        await pilot.press("space", "space")

        app.panel.drop_missing_marks({"hash-b", "hash-c", "hash-d"})
        app.panel.r_torrents = TORRENTS[1:]
        await pilot.pause()

        assert app.panel.marked == {"hash-b"}
        assert app.mark_states[-1] == MarkState(listed=1, hidden=0)

    run_list(test)


def test_hidden_count_is_updated_when_hidden_torrent_is_removed():
    async def test(app, pilot):
        await pilot.press("space", "space")
        app.panel.r_torrents = TORRENTS[1:]
        await pilot.pause()
        assert app.mark_states[-1] == MarkState(listed=1, hidden=1)

        # Hidden torrent a is removed from client: listed torrents are the
        # same, so list isn't updated
        app.panel.drop_missing_marks({"hash-b", "hash-c", "hash-d"})
        app.panel.r_torrents = TORRENTS[1:]
        await pilot.pause()

        assert app.mark_states[-1] == MarkState(listed=1, hidden=0)

    run_list(test)


def test_removed_torrents_are_unmarked():
    async def test(app, pilot):
        await pilot.press("space", "space", "r")

        removed = app.commands(RemoveTorrentCommand)
        assert [names(c.torrents) for c in removed] == [["a", "b"]]

        app.panel.post_message(TorrentRemovedEvent(["hash-a", "hash-b"]))
        await pilot.pause()

        assert app.panel.marked == set()
        assert names(app.panel.page_torrents) == ["c", "d"]
        assert app.panel.get_hl_torrent().name == "c"
        assert app.mark_states[-1] == MarkState(listed=0, hidden=0)

        # Removed torrents can't be marked again before next list update
        await pilot.press("V")
        assert app.panel.marked == {"hash-c", "hash-d"}

    run_list(test)


@pytest.mark.parametrize(
    "cursor,removed,expected",
    [
        # Highlighted torrent is removed: cursor moves to the next one
        ("b", ["b"], "c"),
        # ... or to previous one at the end of list
        ("d", ["d"], "c"),
        ("c", ["c", "d"], "b"),
        # Cursor stays on highlighted torrent
        ("c", ["a", "b"], "c"),
        ("b", ["a", "c"], "b"),
    ],
)
def test_cursor_after_removing_torrents(cursor, removed, expected):
    async def test(app, pilot):
        app.panel.update_page(app.panel.r_torrents, f"hash-{cursor}")
        app.panel.post_message(
            TorrentRemovedEvent([f"hash-{name}" for name in removed])
        )
        await pilot.pause()

        assert app.panel.get_hl_torrent().name == expected

    run_list(test)


def test_removing_torrents_on_other_page_keeps_cursor():
    async def test(app, pilot):
        # Mark a and move to b (page 1), move to c (page 2)
        await pilot.press("space", "j")
        assert app.panel.page_state.current == 1

        app.panel.post_message(TorrentRemovedEvent(["hash-a"]))
        await pilot.pause()

        assert app.panel.get_hl_torrent().name == "c"
        assert app.panel.page_state.total == 2
        assert names(app.panel.r_torrents) == ["b", "c", "d"]

    run_list(test, page_size=2)


def test_mark_is_drawn_in_first_column_without_shifting_item():
    def line_text(panel: TorrentListViewPanel, y: int) -> str:
        return "".join(segment.text for segment in panel.render_line(y))

    async def test(app, pilot):
        unmarked = line_text(app.panel, 1)

        await pilot.press("j", "space")
        marked = line_text(app.panel, 1)

        assert unmarked[0] == " "
        assert marked[0] == MARK
        assert marked[1:] == unmarked[1:]

    run_list(test)
