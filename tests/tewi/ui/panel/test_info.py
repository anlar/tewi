"""Tests for info panel (top status line)."""

import asyncio

import pytest
from textual.app import App, ComposeResult

from src.tewi.torrent.models import ConnectionSecurity
from src.tewi.ui.panel.info import InfoPanel


class InfoApp(App):
    def __init__(self, host: str, security: ConnectionSecurity) -> None:
        super().__init__()
        self.host = host
        self.security = security

    def compose(self) -> ComposeResult:
        yield InfoPanel(
            "3.1.0", "qBittorrent", "5.1.2", self.host, "8080", self.security
        )


def render(host: str, security: ConnectionSecurity):
    """Return (address text, TLS badge text and classes or None)."""
    result = {}

    async def run() -> None:
        app = InfoApp(host, security)
        async with app.run_test():
            columns = list(app.query("#info-panel > .column"))
            result["address"] = str(columns[4].render())
            badges = list(app.query("#tls"))
            result["badge"] = (
                (str(badges[0].render()), set(badges[0].classes))
                if badges
                else None
            )

    asyncio.run(run())
    return result["address"], result["badge"]


@pytest.mark.parametrize(
    "security,text,css_class",
    [
        (ConnectionSecurity.PLAIN, "No TLS", "insecure"),
        (ConnectionSecurity.TLS, "TLS", "secure"),
        (ConnectionSecurity.TLS_UNVERIFIED, "TLS unverified", "insecure"),
    ],
)
def test_tls_badge(security, text, css_class):
    address, badge = render("nas", security)

    assert address == "nas:8080"
    assert badge[0] == text
    assert css_class in badge[1]


def test_no_badge_for_local_connection():
    address, badge = render("localhost", ConnectionSecurity.LOCAL)

    assert address == "localhost:8080"
    assert badge is None


def test_address_is_not_parsed_as_markup():
    address, _ = render("[b]nas", ConnectionSecurity.PLAIN)

    assert address == "[b]nas:8080"
