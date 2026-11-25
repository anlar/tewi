# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for torrent actions running client calls in background thread."""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from textual.app import App, ComposeResult

from src.tewi.app import MainApp
from src.tewi.torrent.models import ClientError
from src.tewi.ui.messages import (
    Confirm,
    EditTorrentCommand,
    Notification,
    RemoveTorrentCommand,
    ToggleTorrentCommand,
    UpdateTorrentCategoryCommand,
    VerifyTorrentCommand,
)
from tests.tewi.ui.helpers import make_list_panel, make_torrent


class TorrentActionApp(App):
    """App running MainApp torrent action worker with fake torrent client."""

    run_torrent_action = MainApp.run_torrent_action
    handle_verify_torrent_command = MainApp.handle_verify_torrent_command

    def __init__(self, error: Exception | None = None) -> None:
        super().__init__()
        self.error = error
        self.calls = []
        self.callbacks = []
        self.notifications = []
        self.client = SimpleNamespace(verify_torrent=self.fake_verify)

    def fake_verify(self, hashes) -> None:
        self.calls.append((hashes, threading.current_thread()))
        if self.error:
            raise self.error

    def on_success(self) -> None:
        self.callbacks.append(threading.current_thread())

    def on_notification(self, event: Notification) -> None:
        self.notifications.append((event.message, event.severity))


@pytest.mark.parametrize(
    "error,expected,callbacks",
    [
        (None, ("Done", "information"), 1),
        (ClientError("boom"), ("Failed:\nboom", "warning"), 0),
        (ConnectionError("lost"), ("Failed:\nlost", "warning"), 0),
    ],
)
def test_action_runs_in_background_thread(error, expected, callbacks):
    async def run() -> None:
        app = TorrentActionApp(error)
        async with app.run_test() as pilot:
            app.run_torrent_action(
                lambda: app.client.verify_torrent("abc"),
                "Done",
                "Failed",
                on_success=app.on_success,
            )
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert len(app.calls) == 1
            assert app.calls[0][1] is not threading.main_thread()
            assert app.notifications == [expected]
            # Callback (e.g. removing torrent from list) runs only after
            # successful call, and in UI thread
            assert app.callbacks == [threading.main_thread()] * callbacks

    asyncio.run(run())


def test_handler_does_not_call_client_in_ui_thread():
    async def run() -> None:
        app = TorrentActionApp()
        async with app.run_test() as pilot:
            app.handle_verify_torrent_command(VerifyTorrentCommand(["abc"]))
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert [hashes for hashes, _ in app.calls] == [["abc"]]
            assert app.calls[0][1] is not threading.main_thread()
            assert app.notifications == [
                ("Torrent sent to verification", "information")
            ]

    asyncio.run(run())


class FakeClient:
    """Torrent client recording calls."""

    def __init__(self) -> None:
        self.calls = []

    def __getattr__(self, name: str):
        return lambda *args, **kwargs: self.calls.append((name, args, kwargs))


class HandlersApp(App):
    """App running MainApp torrent action handlers with fake client."""

    run_torrent_action = MainApp.run_torrent_action
    handle_toggle_torrent_command = MainApp.handle_toggle_torrent_command
    handle_edit_torrent_command = MainApp.handle_edit_torrent_command
    handle_remove_torrent_command = MainApp.handle_remove_torrent_command
    handle_update_torrent_category_command = (
        MainApp.handle_update_torrent_category_command
    )

    def __init__(self) -> None:
        super().__init__()
        self.client = FakeClient()
        self.confirms = []
        self.notifications = []

    def compose(self) -> ComposeResult:
        # Remove handler sends removed torrents to list
        yield make_list_panel()

    def on_confirm(self, event: Confirm) -> None:
        self.confirms.append(event)

    def on_notification(self, event: Notification) -> None:
        self.notifications.append(event.message)


def run_handlers(test) -> None:
    async def run() -> None:
        app = HandlersApp()
        async with app.run_test() as pilot:
            await test(app, pilot)

    asyncio.run(run())


@pytest.mark.parametrize(
    "statuses,expected,message",
    [
        (["stopped"], "start_torrent", "Torrent started"),
        (["seeding"], "stop_torrent", "Torrent stopped"),
        # Several torrents end up in the same state
        (["seeding", "stopped"], "start_torrent", "2 torrents started"),
        (["seeding", "downloading"], "stop_torrent", "2 torrents stopped"),
    ],
)
def test_toggle_starts_torrents_if_any_is_stopped(statuses, expected, message):
    torrents = [
        make_torrent(str(i), status) for i, status in enumerate(statuses)
    ]

    async def test(app, pilot):
        app.handle_toggle_torrent_command(ToggleTorrentCommand(torrents))
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.client.calls == [
            (expected, ([t.hash for t in torrents],), {})
        ]
        assert app.notifications == [message]

    run_handlers(test)


def test_moving_several_torrents_keeps_their_names():
    torrents = [make_torrent("a"), make_torrent("b")]

    async def test(app, pilot):
        app.handle_edit_torrent_command(
            EditTorrentCommand(torrents, None, "/new")
        )
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.client.calls == [
            ("edit_torrent", ("hash-a", "a", "/new"), {}),
            ("edit_torrent", ("hash-b", "b", "/new"), {}),
        ]
        assert app.notifications == ["2 torrents moved"]

    run_handlers(test)


def test_remove_confirmation_lists_names_and_removes_chosen_torrents():
    torrents = [make_torrent(name) for name in ("a", "[b]", "c", "d", "e")]

    async def test(app, pilot):
        app.handle_remove_torrent_command(RemoveTorrentCommand(torrents))
        await pilot.pause()

        (confirm,) = app.confirms
        assert confirm.message == "Remove 5 torrents?"
        assert confirm.items == ["a", "[b]", "c", "and 2 more"]

        confirm.check_quit(True)
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.client.calls == [
            (
                "remove_torrent",
                ([t.hash for t in torrents],),
                {"delete_data": False},
            )
        ]
        assert app.notifications == ["5 torrents removed"]

    run_handlers(test)


def test_category_with_braces_is_shown_literally():
    """Category name comes from torrent client: it must not be read as
    format string in message for several torrents."""

    async def test(app, pilot):
        app.handle_update_torrent_category_command(
            UpdateTorrentCategoryCommand(["hash-a", "hash-b"], "{x} {0}")
        )
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.notifications == ["Category of 2 torrents set to: {x} {0}"]

    run_handlers(test)
