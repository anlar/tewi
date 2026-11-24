"""Tests for handling links from remote sources (search providers).

Links must be magnet or HTTP(S) only: other values could open local files
or custom URL handlers, or be read as local file path when adding torrent.
"""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from textual.app import App

from src.tewi.app import MainApp
from src.tewi.torrent.models import ClientError
from src.tewi.ui.messages import AddTorrentFromWebSearchCommand, Notification

HTTP_URLS = [
    "https://example.com/torrent/1",
    "http://example.com/details?id=1&x=2",
    "HTTPS://EXAMPLE.COM/",
]

UNSAFE_URLS = [
    "",
    "file:///etc/passwd",
    "/home/user/.ssh/id_ed25519",
    "~/.ssh/id_ed25519",
    r"\\attacker\share\x.torrent",
    "smb://attacker/share",
    "javascript:alert(1)",
    "steam://run/1",
    "https://example.com/ x",
]


@pytest.fixture
def app(monkeypatch):
    """MainApp without running or connecting to torrent client."""
    opened = []
    monkeypatch.setattr(
        App, "open_url", lambda self, url, new_tab=True: opened.append(url)
    )
    app = MainApp.__new__(MainApp)
    app.messages = []
    app.post_message = app.messages.append
    app.opened = opened
    return app


class TestMainAppOpenUrl:
    """MainApp.open_url is used for all links (widgets and key bindings)."""

    @pytest.mark.parametrize("url", HTTP_URLS)
    def test_http_url_is_opened(self, app, url):
        app.open_url(url)

        assert app.opened == [url]
        assert app.messages == []

    def test_url_is_stripped(self, app):
        app.open_url(" https://example.com/\n")

        assert app.opened == ["https://example.com/"]

    @pytest.mark.parametrize("url", UNSAFE_URLS)
    def test_unsafe_url_is_rejected(self, app, url):
        app.open_url(url)

        assert app.opened == []
        assert [m.severity for m in app.messages] == ["warning"]


class TestAddTorrentFromWebSearch:
    @pytest.fixture
    def fake_app(self):
        added = []
        messages = []
        return SimpleNamespace(
            add_torrent=lambda value, msg: added.append(value),
            post_message=messages.append,
            added=added,
            messages=messages,
        )

    def handle(self, fake_app, link: str) -> None:
        event = AddTorrentFromWebSearchCommand(link)
        MainApp.handle_add_torrent_from_websearch_command(fake_app, event)

    @pytest.mark.parametrize(
        "link",
        [
            "magnet:?xt=urn:btih:" + "a" * 40,
            "https://example.com/x.torrent",
            "http://localhost:9117/dl/x?apikey=1",
        ],
    )
    def test_link_is_added(self, fake_app, link):
        self.handle(fake_app, link)

        assert fake_app.added == [link]
        assert fake_app.messages == []

    @pytest.mark.parametrize(
        "link",
        [
            "~/.ssh/id_ed25519",
            "/etc/passwd",
            "file:///etc/passwd",
            "a" * 40,
            "",
        ],
    )
    def test_non_link_is_rejected(self, fake_app, link):
        self.handle(fake_app, link)

        assert fake_app.added == []
        assert [m.severity for m in fake_app.messages] == ["warning"]


class AddTorrentApp(App):
    """App running MainApp.add_torrent worker with fake torrent client."""

    add_torrent = MainApp.add_torrent

    def __init__(
        self,
        error: Exception | None = None,
        errors: dict[str, Exception] | None = None,
    ) -> None:
        super().__init__()
        self.error = error
        self.errors = errors or {}
        self.threads = []
        self.added = []
        self.notifications = []
        self.client = SimpleNamespace(add_torrent=self.fake_add_torrent)

    def fake_add_torrent(self, value: str) -> None:
        self.threads.append(threading.current_thread())
        if self.error:
            raise self.error
        if value in self.errors:
            raise self.errors[value]
        self.added.append(value)

    def on_notification(self, event: Notification) -> None:
        self.notifications.append((event.message, event.severity))


@pytest.mark.parametrize(
    "error,expected",
    [
        (None, ("Added", "information")),
        (ClientError("boom"), ("Failed to add torrent:\nboom", "warning")),
    ],
)
def test_add_torrent_runs_in_background_thread(error, expected):
    async def run() -> None:
        app = AddTorrentApp(error)
        async with app.run_test() as pilot:
            app.add_torrent("https://example.com/x.torrent", "Added")
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert len(app.threads) == 1
            assert app.threads[0] is not threading.main_thread()
            assert app.notifications == [expected]

    asyncio.run(run())


def run_add_torrent(value: str, **kwargs) -> AddTorrentApp:
    async def run() -> AddTorrentApp:
        app = AddTorrentApp(**kwargs)
        async with app.run_test() as pilot:
            app.add_torrent(value, "Added")
            await app.workers.wait_for_complete()
            await pilot.pause()
        return app

    return asyncio.run(run())


MAGNET_A = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=a"
MAGNET_B = "magnet:?xt=urn:btih:" + "b" * 40 + "&dn=b"
MAGNET_C = "magnet:?xt=urn:btih:" + "c" * 40 + "&dn=c"


def test_add_torrent_adds_each_line_separately():
    app = run_add_torrent(f"{MAGNET_A}\n\n  {MAGNET_B}  \n{MAGNET_C}\n")

    assert app.added == [MAGNET_A, MAGNET_B, MAGNET_C]
    assert app.notifications == [("3 new torrents were added", "information")]


def test_add_torrent_single_line_ignores_surrounding_blank_lines():
    app = run_add_torrent(f"\n{MAGNET_A}\n")

    assert app.added == [MAGNET_A]
    assert app.notifications == [("Added", "information")]


def test_add_torrent_reports_failed_lines_and_adds_others():
    app = run_add_torrent(
        f"{MAGNET_A}\n/no/such.torrent\n{MAGNET_C}",
        errors={
            "/no/such.torrent": FileNotFoundError(),
            MAGNET_C: ClientError("duplicate"),
        },
    )

    assert app.added == [MAGNET_A]
    assert app.notifications == [
        (
            "Added 1 of 3 torrents, failed 2:\n"
            "File not found /no/such.torrent\nduplicate",
            "warning",
        )
    ]


def test_add_torrent_limits_listed_errors():
    values = [f"/no/{i}.torrent" for i in range(5)]
    app = run_add_torrent(
        "\n".join(values),
        errors={v: ClientError(f"err {i}") for i, v in enumerate(values)},
    )

    assert app.notifications == [
        (
            "Added 0 of 5 torrents, failed 5:\nerr 0\nerr 1\nerr 2\nand 2 more",
            "warning",
        )
    ]
