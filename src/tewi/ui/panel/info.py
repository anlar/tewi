from time import time

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from ...torrent.models import ConnectionSecurity
from ...util.log import log_time
from ..util import (
    print_time_ago,
    subtitle_keys,
)
from ..widget.common import ReactiveLayoutLabel

# Badge text and CSS class for connection security (none for local
# connection, as its traffic never leaves the machine)
TLS_BADGES: dict[ConnectionSecurity, tuple[str, str]] = {
    ConnectionSecurity.PLAIN: ("No TLS", "insecure"),
    ConnectionSecurity.TLS: ("TLS", "secure"),
    ConnectionSecurity.TLS_UNVERIFIED: ("TLS unverified", "insecure"),
}


class InfoPanel(Static):
    r_connected = reactive(True)
    r_connected_ts = reactive(time)
    r_connected_error_ts = reactive(None)

    r_connection = reactive("")

    @log_time
    def __init__(
        self,
        app_version: str,
        client_name: str,
        client_version: str,
        host: str,
        port: str,
        security: ConnectionSecurity = ConnectionSecurity.LOCAL,
    ):
        self.app_version = app_version
        self.client_name = client_name
        self.client_version = client_version
        self.host = host
        self.port = port
        self.security = security

        super().__init__()

    @log_time
    def compose(self) -> ComposeResult:
        with Horizontal(id="info-panel"):
            yield Static(f"Tewi {self.app_version}", classes="column")
            yield Static("»»»", classes="column delimiter")
            yield Static(
                f"{self.client_name} {self.client_version}", classes="column"
            )
            yield Static("»»»", classes="column delimiter")
            yield Static(
                f"{self.host}:{self.port}", markup=False, classes="column"
            )
            if self.security in TLS_BADGES:
                text, css_class = TLS_BADGES[self.security]
                yield Static(text, id="tls", classes=f"column {css_class}")
            yield ReactiveLayoutLabel(
                markup=True, id="connection", classes="column"
            ).data_bind(name=InfoPanel.r_connection)
            yield Static("", classes="column space")
            yield Static(
                subtitle_keys(("?", "Help"), ("Q", "Quit")), classes="column"
            )

    @log_time
    def on_mount(self) -> None:
        self._update_connection()

    @log_time
    def watch_r_connected(self, status: str) -> None:
        self._update_connection()

    @log_time
    def watch_r_connected_ts(self, ts) -> None:
        self._update_connection()

    @log_time
    def watch_r_connected_error_ts(self, ts) -> None:
        self._update_connection()

    @log_time
    def _update_connection(self) -> None:
        if self.r_connected:
            self.r_connection = ""
        else:
            time_ago = print_time_ago(self.r_connected_ts)
            self.r_connection = f"Offline [dim]·[/] updated {time_ago}"

        # shown as badge only when disconnected (see app.tcss)
        for label in self.query("#connection"):
            label.set_class(not self.r_connected, "disconnected")
