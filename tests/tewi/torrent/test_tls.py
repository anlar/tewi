"""Tests for TLS (HTTPS) connections to torrent client daemons.

Clients are connected to local HTTPS server with self-signed certificate,
which records requests received over TLS (every response is an error, so
connection itself fails after request is received).
"""

import logging
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from src.tewi.torrent import factory
from src.tewi.torrent.clients.deluge import DelugeClient
from src.tewi.torrent.clients.qbittorrent import QBittorrentClient
from src.tewi.torrent.clients.rtorrent import RTorrentClient
from src.tewi.torrent.clients.transmission import TransmissionClient
from src.tewi.torrent.factory import create_client, split_host_scheme
from src.tewi.torrent.models import (
    ClientError,
    ConnectionSecurity,
    TlsOptions,
)
from src.tewi.torrent.util import connection_security, is_loopback


class TestTlsOptions:
    def test_defaults(self):
        tls = TlsOptions()

        assert tls.enabled is False
        assert tls.requests_verify is True

    def test_ca_cert_used_for_verification(self):
        assert TlsOptions(True, True, "/ca.pem").requests_verify == "/ca.pem"

    def test_disabled_verification_ignores_ca_cert(self):
        assert TlsOptions(True, False, "/ca.pem").requests_verify is False


class TestSplitHostScheme:
    @pytest.mark.parametrize(
        "host,expected_host,expected_tls",
        [
            ("nas", "nas", False),
            ("https://nas", "nas", True),
            ("HTTPS://nas/", "nas", True),
            ("http://nas", "nas", False),
            ("192.168.1.2", "192.168.1.2", False),
        ],
    )
    def test_scheme(self, host, expected_host, expected_tls):
        result_host, tls = split_host_scheme(host, TlsOptions())

        assert result_host == expected_host
        assert tls.enabled is expected_tls

    def test_http_scheme_overrides_tls_option(self):
        _, tls = split_host_scheme("http://nas", TlsOptions(enabled=True))

        assert tls.enabled is False

    def test_unsupported_scheme(self):
        with pytest.raises(ClientError, match="Unsupported scheme"):
            split_host_scheme("ftp://nas", TlsOptions())


class TestIsLoopback:
    @pytest.mark.parametrize(
        "host", ["localhost", "LOCALHOST", "127.0.0.1", "127.1.2.3", "::1"]
    )
    def test_loopback(self, host):
        assert is_loopback(host) is True

    @pytest.mark.parametrize(
        "host", ["nas", "192.168.1.2", "10.0.0.1", "example.com", "::2"]
    )
    def test_remote(self, host):
        assert is_loopback(host) is False

    def test_bracketed_ipv6(self):
        assert is_loopback("[::1]") is True


class TestCreateClientTls:
    """Test TLS handling in factory, with fake client classes."""

    @pytest.fixture
    def created(self, monkeypatch):
        calls = []

        def fake(**kwargs):
            calls.append(kwargs)
            return kwargs

        # Don't disable urllib3 warnings for other tests
        monkeypatch.setattr(
            factory.urllib3, "disable_warnings", lambda *args: None
        )
        for name in [
            "TransmissionClient",
            "QBittorrentClient",
            "DelugeClient",
            "RTorrentClient",
        ]:
            monkeypatch.setattr(factory, name, fake)
        return calls

    @pytest.mark.parametrize(
        "client_type", ["transmission", "qbittorrent", "deluge", "rtorrent"]
    )
    def test_tls_passed_to_client(self, created, client_type):
        tls = TlsOptions(enabled=True)

        create_client(client_type, "nas", "443", tls=tls)

        assert created[0]["host"] == "nas"
        assert created[0]["tls"] == tls

    def test_https_host_enables_tls(self, created):
        create_client("transmission", "https://nas", "443")

        assert created[0]["host"] == "nas"
        assert created[0]["tls"].enabled is True

    def test_ca_cert_path_expanded(self, created, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / "ca.pem").write_text("cert")
        tls = TlsOptions(enabled=True, ca_cert="~/ca.pem")

        create_client("deluge", "nas", "8112", tls=tls)

        assert created[0]["tls"].ca_cert == str(tmp_path / "ca.pem")

    def test_missing_ca_cert(self, created, tmp_path):
        tls = TlsOptions(enabled=True, ca_cert=str(tmp_path / "missing.pem"))

        with pytest.raises(ClientError, match="CA certificate file not found"):
            create_client("deluge", "nas", "8112", tls=tls)

    def test_warning_for_password_to_remote_host(self, created, caplog):
        with caplog.at_level(logging.WARNING, logger="tewi"):
            create_client("transmission", "nas", "9091", password="secret")

        assert "without TLS" in caplog.text

    @pytest.mark.parametrize(
        "host,password,tls",
        [
            ("localhost", "secret", TlsOptions()),
            ("127.0.0.1", "secret", TlsOptions()),
            ("nas", None, TlsOptions()),
            ("nas", "secret", TlsOptions(enabled=True)),
        ],
    )
    def test_no_warning(self, created, caplog, host, password, tls):
        with caplog.at_level(logging.WARNING, logger="tewi"):
            create_client("transmission", host, "9091", None, password, tls=tls)

        assert caplog.text == ""

    def test_warning_for_disabled_verification(self, created, caplog):
        tls = TlsOptions(enabled=True, verify=False)

        with caplog.at_level(logging.WARNING, logger="tewi"):
            create_client("transmission", "nas", "9091", tls=tls)

        assert "verification is disabled" in caplog.text


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    """Generate self-signed certificate for localhost/127.0.0.1."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not available")

    path = tmp_path_factory.mktemp("tls")
    cert, key = path / "cert.pem", path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


class _RecordingHandler(BaseHTTPRequestHandler):
    """Record requests received over TLS, respond with error."""

    def _handle(self):
        self.server.requests.append((self.command, self.path))
        self.send_response(500)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def log_message(self, *args):
        pass


class _TLSServer(ThreadingHTTPServer):
    def __init__(self, context: ssl.SSLContext) -> None:
        super().__init__(("127.0.0.1", 0), _RecordingHandler)
        self.context = context
        self.requests = []

    def get_request(self):
        sock, addr = super().get_request()
        return self.context.wrap_socket(sock, server_side=True), addr

    def handle_error(self, request, client_address):
        # Rejected handshakes are expected in tests
        pass


@pytest.fixture
def https_server(certificate):
    cert, key = certificate
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)

    server = _TLSServer(context)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def connect(client_type: str, server: _TLSServer, tls: TlsOptions) -> None:
    """Connect client to server, ignoring errors (server always fails)."""
    port = str(server.server_address[1])
    kwargs = {"host": "127.0.0.1", "port": port, "tls": tls}
    if client_type != "qbittorrent":
        kwargs["path"] = "/RPC2" if client_type == "rtorrent" else None

    client_class = {
        "transmission": TransmissionClient,
        "qbittorrent": QBittorrentClient,
        "deluge": DelugeClient,
        "rtorrent": RTorrentClient,
    }[client_type]
    try:
        client_class(**kwargs)
    except Exception:
        pass


CLIENT_TYPES = ["transmission", "qbittorrent", "deluge", "rtorrent"]


@pytest.mark.parametrize("client_type", CLIENT_TYPES)
class TestClientTlsConnection:
    def test_untrusted_certificate_rejected(self, client_type, https_server):
        """Certificate is verified by default (no fallback to HTTP)."""
        connect(client_type, https_server, TlsOptions(enabled=True))

        assert https_server.requests == []

    def test_ca_cert_trusted(self, client_type, https_server, certificate):
        cert, _ = certificate
        tls = TlsOptions(enabled=True, ca_cert=str(cert))

        connect(client_type, https_server, tls)

        assert https_server.requests

    @pytest.mark.filterwarnings(
        "ignore::urllib3.exceptions.InsecureRequestWarning"
    )
    def test_verification_disabled(self, client_type, https_server):
        tls = TlsOptions(enabled=True, verify=False)

        connect(client_type, https_server, tls)

        assert https_server.requests


def test_rtorrent_tls_requires_http_path():
    with pytest.raises(ClientError, match="SCGI"):
        RTorrentClient("127.0.0.1", "5000", tls=TlsOptions(enabled=True))


class TestConnectionSecurity:
    @pytest.mark.parametrize(
        "host,tls,verified,expected",
        [
            ("localhost", False, True, ConnectionSecurity.LOCAL),
            ("127.0.0.1", False, True, ConnectionSecurity.LOCAL),
            # Private network isn't trusted (e.g. public Wi-Fi)
            ("192.168.1.2", False, True, ConnectionSecurity.PLAIN),
            ("nas", False, True, ConnectionSecurity.PLAIN),
            ("nas", True, True, ConnectionSecurity.TLS),
            ("localhost", True, True, ConnectionSecurity.TLS),
            ("nas", True, False, ConnectionSecurity.TLS_UNVERIFIED),
        ],
    )
    def test_security(self, host, tls, verified, expected):
        assert connection_security(host, tls, verified) is expected


def bare(client_class, **attrs):
    """Client instance without connecting, with given attributes."""
    client = client_class.__new__(client_class)
    for name, value in attrs.items():
        setattr(client, name, value)
    return client


class TestClientConnectionSecurity:
    @pytest.mark.parametrize("client_class", [TransmissionClient, DelugeClient])
    @pytest.mark.parametrize(
        "tls,expected",
        [
            (TlsOptions(), ConnectionSecurity.PLAIN),
            (TlsOptions(enabled=True), ConnectionSecurity.TLS),
            (
                TlsOptions(enabled=True, verify=False),
                ConnectionSecurity.TLS_UNVERIFIED,
            ),
        ],
    )
    def test_tls_options(self, client_class, tls, expected):
        client = bare(client_class, _host="nas", _tls=tls)

        assert client.connection_security() is expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("http://nas:8000/RPC2", ConnectionSecurity.PLAIN),
            # HTTPS on port 443 without TLS option
            ("https://nas:443/RPC2", ConnectionSecurity.TLS),
            ("http://localhost:5000/", ConnectionSecurity.LOCAL),
        ],
    )
    def test_rtorrent_uses_actual_scheme(self, url, expected):
        client = bare(
            RTorrentClient,
            _host=url.split("//")[1].split(":")[0],
            _tls=TlsOptions(),
            _url=url,
        )

        assert client.connection_security() is expected

    @pytest.mark.parametrize(
        "base_url,verify,expected",
        [
            ("http://nas:8080/", True, ConnectionSecurity.PLAIN),
            # Library switched to HTTPS without TLS option
            ("https://nas:8080/", True, ConnectionSecurity.TLS),
            ("https://nas:8080/", False, ConnectionSecurity.TLS_UNVERIFIED),
            (None, True, ConnectionSecurity.PLAIN),
        ],
    )
    def test_qbittorrent_uses_detected_scheme(self, base_url, verify, expected):
        api = SimpleNamespace(
            _url=SimpleNamespace(_base_url=base_url),
            _VERIFY_WEBUI_CERTIFICATE=verify,
        )
        client = bare(QBittorrentClient, _host="nas", client=api)

        assert client.connection_security() is expected
