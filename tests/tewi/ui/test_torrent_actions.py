"""Tests for torrent actions running client calls in background thread."""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from textual.app import App

from src.tewi.app import MainApp
from src.tewi.torrent.models import ClientError
from src.tewi.ui.messages import Notification, VerifyTorrentCommand


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
            app.handle_verify_torrent_command(VerifyTorrentCommand("abc"))
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert [hashes for hashes, _ in app.calls] == ["abc"]
            assert app.calls[0][1] is not threading.main_thread()
            assert app.notifications == [
                ("Torrent sent to verification", "information")
            ]

    asyncio.run(run())
