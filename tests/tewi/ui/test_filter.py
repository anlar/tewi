"""Tests for filtering torrents by state, category and label."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from textual import on
from textual.app import App

from src.tewi.app import MainApp
from src.tewi.torrent.base import ClientCapability
from src.tewi.ui.dialog.torrent.filter import FilterDialog
from src.tewi.ui.dialog.torrent.filter_tag import FilterTagDialog
from src.tewi.ui.messages import (
    FilterTagUpdatedEvent,
    FilterUpdatedEvent,
    OpenFilterTagCommand,
)
from src.tewi.ui.models import (
    FilterState,
    TagType,
    count_tags,
    get_filter_by_id,
    parse_filter,
)
from src.tewi.ui.panel.state import StatePanel
from tests.tewi.ui.helpers import make_torrent

TORRENTS = [
    replace(make_torrent("a"), category="movies", labels=["hd", "hd"]),
    replace(make_torrent("b"), labels=["hd", "Anime"]),
    make_torrent("c"),
]

COUNTS = {"hd": 2, "Anime": 1}


def test_names():
    a, b, c = TORRENTS

    assert TagType.CATEGORY.names(a) == {"movies"}
    assert TagType.CATEGORY.names(b) == set()
    assert TagType.LABEL.names(a) == {"hd"}
    assert TagType.LABEL.names(c) == set()


def test_count_tags_sorted_by_name():
    # Duplicate label of torrent is counted once
    assert list(count_tags(TORRENTS, TagType.LABEL).items()) == [
        ("Anime", 1),
        ("hd", 2),
    ]
    assert count_tags(TORRENTS, TagType.CATEGORY) == {"movies": 1}


def test_count_tags_includes_current_filter():
    # Shown in dialog even if no torrent has it
    assert count_tags(TORRENTS, TagType.LABEL, "old") == {
        "Anime": 1,
        "hd": 2,
        "old": 0,
    }
    assert count_tags(TORRENTS, TagType.LABEL, "hd") == {"Anime": 1, "hd": 2}


@pytest.mark.parametrize(
    "value,state,tags",
    [
        ("", "all", {}),
        ("seeding", "seeding", {}),
        ("checking", "checking", {}),
        ("Seeding", "seeding", {}),
        ("label:hd", "all", {TagType.LABEL: "hd"}),
        (
            " seeding , Category: a:b ,label:hd,",
            "seeding",
            {TagType.CATEGORY: "a:b", TagType.LABEL: "hd"},
        ),
    ],
)
def test_parse_filter(value, state, tags):
    assert parse_filter(value) == (get_filter_by_id(state), tags)


@pytest.mark.parametrize(
    "value,error",
    [
        ("foo", "unknown filter 'foo'"),
        ("tag:hd", "unknown filter 'tag:hd'"),
        ("label:", "empty name"),
        ("seeding,active", "more than one state"),
        ("label:a,label:b", "more than one label"),
    ],
)
def test_parse_filter_invalid(value, error):
    with pytest.raises(ValueError, match=error):
        parse_filter(value)


class DialogApp(App):
    def __init__(self, screen) -> None:
        super().__init__()
        self.dialog = screen
        self.events: list = []

    def on_mount(self) -> None:
        self.push_screen(self.dialog)

    @on(FilterUpdatedEvent)
    @on(FilterTagUpdatedEvent)
    @on(OpenFilterTagCommand)
    def record(self, event) -> None:
        self.events.append(event)


def run_dialog(screen, keys: list[str]) -> list:
    async def run() -> list:
        app = DialogApp(screen)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            await pilot.press(*keys)
            await pilot.pause()
            assert app.screen is not screen
        return app.events

    return asyncio.run(run())


def test_filter_dialog_selects_state():
    events = run_dialog(FilterDialog(list(TagType)), ["h"])

    assert events == [FilterUpdatedEvent(get_filter_by_id("checking"))]


def test_filter_dialog_opens_tag_filter():
    tag_types = list(TagType)

    assert run_dialog(FilterDialog(tag_types), ["c"]) == [
        OpenFilterTagCommand(TagType.CATEGORY)
    ]
    assert run_dialog(FilterDialog(tag_types), ["l"]) == [
        OpenFilterTagCommand(TagType.LABEL)
    ]


def test_filter_dialog_hides_tag_types_not_supported_by_client():
    events = run_dialog(FilterDialog([TagType.LABEL]), ["c", "x"])

    assert events == []


def test_tag_dialog_selects_name():
    dialog = FilterTagDialog(TagType.LABEL, COUNTS, None)

    assert run_dialog(dialog, ["j", "j", "enter"]) == [
        FilterTagUpdatedEvent(TagType.LABEL, "Anime")
    ]


def test_tag_dialog_starts_at_current_name_and_clears_it():
    dialog = FilterTagDialog(TagType.LABEL, COUNTS, "Anime")
    assert run_dialog(dialog, ["enter"]) == [
        FilterTagUpdatedEvent(TagType.LABEL, "Anime")
    ]

    dialog = FilterTagDialog(TagType.LABEL, COUNTS, "Anime")
    assert run_dialog(dialog, ["k", "k", "enter"]) == [
        FilterTagUpdatedEvent(TagType.LABEL, None)
    ]


def test_tag_dialog_close_keeps_filter():
    dialog = FilterTagDialog(TagType.LABEL, COUNTS, "hd")

    assert run_dialog(dialog, ["x"]) == []


def test_state_panel_shows_tag_filter():
    async def run() -> None:
        app = App()
        async with app.run_test() as pilot:
            panel = StatePanel()
            await app.mount(panel)
            panel.r_filter_state = FilterState(
                get_filter_by_id("seeding"),
                3,
                "foo",
                ((TagType.CATEGORY, "movies"), (TagType.LABEL, "hd")),
            )
            await pilot.pause()

            assert panel.r_filter == (
                'Filter: Seeding + "foo" + Category: movies + Label: hd (3)'
            )

            panel.r_filter_state = FilterState(
                get_filter_by_id("all"), 2, "", ((TagType.LABEL, "hd"),)
            )
            await pilot.pause()

            assert panel.r_filter == "Filter: Label: hd (2)"

    asyncio.run(run())


def test_filter_tags_not_supported_by_client_are_ignored():
    client = SimpleNamespace(
        capable=lambda c: c == ClientCapability.LABEL,
    )
    app = SimpleNamespace(client=client, c_type="transmission")
    app.supported_tag_types = lambda: MainApp.supported_tag_types(app)

    tags = {TagType.CATEGORY: "movies", TagType.LABEL: "hd"}

    assert MainApp.supported_filter_tags(app, tags) == {TagType.LABEL: "hd"}
