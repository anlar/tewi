from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from ...util.log import log_time
from ..util import subtitle_keys


class InfoPanel(Static):
    @log_time
    def __init__(
        self,
        app_version: str,
        client_name: str,
        client_version: str,
        host: str,
        port: str,
    ):
        self.app_version = app_version
        self.client_name = client_name
        self.client_version = client_version
        self.host = host
        self.port = port

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
            yield Static(f"{self.host}:{self.port}", classes="column")
            yield Static("", classes="column space")
            yield Static(
                subtitle_keys(("?", "Help"), ("Q", "Quit")), classes="column"
            )
