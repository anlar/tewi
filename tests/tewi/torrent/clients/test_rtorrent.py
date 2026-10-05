#!/usr/bin/env python3

# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2024  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import http.server
import socket
import subprocess
import threading
import xmlrpc.client
from datetime import timedelta

import pytest

from src.tewi.torrent.base import ClientCapability
from src.tewi.torrent.clients.rtorrent import (
    DELETE_SCRIPT,
    MOVE_CONFLICT_SCRIPT,
    MOVE_SCRIPT,
    RPCFaultError,
    RTorrentClient,
)
from src.tewi.torrent.models import (
    ClientError,
    TorrentFilePriority,
    TorrentPeerState,
)

HASH = "5B1E0D988FC7A0C9E99BD852071681A59974B39F"


def make_torrent() -> dict:
    """Create fake rTorrent download state (multi-file torrent)."""
    return {
        "d.hash": HASH,
        "d.name": "ubuntu",
        "d.state": 1,
        "d.is_active": 1,
        "d.complete": 0,
        "d.hashing": 0,
        "d.size_bytes": 1000,
        "d.completed_bytes": 250,
        "d.left_bytes": 750,
        "d.up.rate": 5,
        "d.down.rate": 10,
        "d.ratio": 1500,
        "d.peers_connected": 3,
        "d.peers_accounted": 1,
        "d.peers_complete": 2,
        "d.up.total": 100,
        "d.priority": 3,
        "d.load_date": 1791142731,
        "d.timestamp.started": 1791142731,
        "d.timestamp.finished": 0,
        "d.directory": "/data/download/ubuntu",
        "d.is_multi_file": 1,
        "d.custom1": "linux%20iso",
        "d.size_chunks": 4,
        "d.chunk_size": 256,
        "d.is_private": 0,
        "d.down.total": 250,
        "d.message": "",
        "d.free_diskspace": 5000,
        "d.is_meta": 0,
        "custom": {
            "tewi_labels": "one,two",
            "comment": "VRS24mrker" + "hello%20world",
        },
        "files": [
            {
                "f.path": "a.bin",
                "f.size_bytes": 600,
                "f.completed_chunks": 1,
                "f.size_chunks": 3,
                "f.priority": 1,
                "f.frozen_path": "",  # closed torrent
            },
            {
                "f.path": "sub/b.bin",
                "f.size_bytes": 400,
                "f.completed_chunks": 2,
                "f.size_chunks": 2,
                "f.priority": 0,
                "f.frozen_path": "",
            },
        ],
        "peers": [
            {
                "p.address": "10.0.0.1",
                "p.port": 6881,
                "p.client_version": "Transmission 4.0",
                "p.completed_percent": 50,
                "p.is_encrypted": 1,
                "p.is_obfuscated": 0,
                "p.is_incoming": 1,
                "p.is_snubbed": 0,
                "p.down_rate": 10,
                "p.up_rate": 0,
            }
        ],
        "trackers": [
            {
                "t.url": "http://tracker/announce",
                "t.group": 0,
                "t.is_enabled": 1,
                "t.is_busy": 0,
                "t.scrape_complete": 7,
                "t.scrape_incomplete": 3,
                "t.scrape_downloaded": 20,
                "t.scrape_time_last": 1791142731,
                "t.latest_sum_peers": 10,
                "t.success_counter": 1,
                "t.failed_counter": 0,
                "t.success_time_last": 1791142731,
                "t.activity_time_next": 1791144531,
            },
            {
                "t.url": "dht://",
                "t.group": 1,
                "t.is_enabled": 1,
                "t.is_busy": 0,
                "t.scrape_complete": 0,
                "t.scrape_incomplete": 0,
                "t.scrape_downloaded": 0,
                "t.scrape_time_last": 0,
                "t.latest_sum_peers": 0,
                "t.success_counter": 0,
                "t.failed_counter": 0,
                "t.success_time_last": 0,
                "t.activity_time_next": 0,
            },
        ],
    }


class FakeRTorrent:
    """In-memory rTorrent model answering XML-RPC methods."""

    GLOBALS = {
        "system.client_version": "0.9.8",
        "directory.default": "/data/download/",
        "throttle.global_up.rate": 5,
        "throttle.global_down.rate": 10,
        "throttle.global_up.max_rate": 0,
        "throttle.global_down.max_rate": 2048,
        "throttle.global_up.total": 100,
        "throttle.global_down.total": 400,
        "network.port_range": "50000-50000",
        "dht.port": 6881,
        "session.path": "/data/session/",
    }

    def __init__(self) -> None:
        self.torrents = {HASH: make_torrent()}
        self.calls = []
        self.loaded = []
        self.fail_methods = set()
        self.capture_output = ""

    def _get(self, hash: str) -> dict:
        try:
            return self.torrents[hash.upper()]
        except KeyError:
            raise xmlrpc.client.Fault(-501, "Could not find info-hash.")

    def dispatch(self, method: str, params: tuple):
        self.calls.append((method, params))

        if method in self.fail_methods:
            raise xmlrpc.client.Fault(-503, f"{method} failed")

        if method in self.GLOBALS:
            return self.GLOBALS[method]

        handler = getattr(self, "_" + method.replace(".", "_"), None)
        if handler:
            return handler(*params)

        return self._torrent_method(method, params)

    def _system_multicall(self, calls: list) -> list:
        results = []
        for c in calls:
            try:
                results.append([self.dispatch(c["methodName"], c["params"])])
            except xmlrpc.client.Fault as e:
                results.append(
                    {"faultCode": e.faultCode, "faultString": e.faultString}
                )
        return results

    def _download_list(self, target: str) -> list:
        return list(self.torrents)

    def _d_multicall2(self, target: str, view: str, *fields: str) -> list:
        return [
            [self._field(t, f) for f in fields] for t in self.torrents.values()
        ]

    def _sub_multicall(self, key: str, hash: str, fields: tuple) -> list:
        rows = self._get(hash)[key]
        return [[r[f.rstrip("=")] for f in fields] for r in rows]

    def _f_multicall(self, hash: str, target: str, *fields: str) -> list:
        return self._sub_multicall("files", hash, fields)

    def _p_multicall(self, hash: str, target: str, *fields: str) -> list:
        return self._sub_multicall("peers", hash, fields)

    def _t_multicall(self, hash: str, target: str, *fields: str) -> list:
        return self._sub_multicall("trackers", hash, fields)

    def _load_start(self, target: str, value) -> int:
        self.loaded.append(("load.start", value))
        return 0

    def _load_raw_start(self, target: str, value) -> int:
        self.loaded.append(("load.raw_start", value))
        return 0

    def _execute_throw(self, *args: str) -> int:
        return 0

    def _execute_throw_bg(self, *args: str) -> int:
        return 0

    def _execute_capture(self, *args: str) -> str:
        return self.capture_output

    def _f_priority_set(self, target: str, value: int) -> int:
        hash, _, idx = target.partition(":f")
        self._get(hash)["files"][int(idx)]["f.priority"] = value
        return 0

    def _d_erase(self, hash: str) -> int:
        self._get(hash)
        del self.torrents[hash.upper()]
        return 0

    def _d_custom(self, hash: str, key: str) -> str:
        return self._get(hash)["custom"].get(key, "")

    def _d_custom_set(self, hash: str, key: str, value: str) -> int:
        self._get(hash)["custom"][key] = value
        return 0

    def _d_directory_set(self, hash: str, value: str) -> int:
        t = self._get(hash)
        t["d.directory"] = f"{value}/{t['d.name']}"
        return 0

    def _torrent_method(self, method: str, params: tuple):
        """Handle simple getters, setters and state commands."""
        t = self._get(params[0])
        updates = {
            "d.custom1.set": {"d.custom1": params[1:]},
            "d.priority.set": {"d.priority": params[1:]},
            "d.start": {"d.state": [1]},
            "d.resume": {"d.is_active": [1]},
            "d.stop": {"d.state": [0], "d.is_active": [0]},
            "d.close": {},
            "d.check_hash": {},
            "d.tracker_announce": {},
            "d.update_priorities": {},
        }

        if method in updates:
            for key, value in updates[method].items():
                t[key] = value[0]
            return 0
        if method in t:
            return t[method]
        raise xmlrpc.client.Fault(-506, f"Method '{method}' not defined")

    @staticmethod
    def _field(t: dict, field: str):
        method, _, arg = field.partition("=")
        if method == "d.custom":
            return t["custom"].get(arg, "")
        return t[method]


class FakeSCGIServer:
    """Minimal SCGI server forwarding XML-RPC calls to FakeRTorrent."""

    def __init__(self, backend: FakeRTorrent) -> None:
        self.backend = backend
        self.sock = socket.create_server(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                self._handle(conn)

    def _handle(self, conn: socket.socket) -> None:
        data = b""
        while b"," not in data:
            data += conn.recv(65536)
        length, _, rest = data.partition(b":")
        headers = rest[: int(length)].split(b"\x00")
        content_length = int(headers[headers.index(b"CONTENT_LENGTH") + 1])
        body = rest[int(length) + 1 :]
        while len(body) < content_length:
            body += conn.recv(65536)

        params, method = xmlrpc.client.loads(body)
        try:
            result = xmlrpc.client.dumps(
                (self.backend.dispatch(method, params),), methodresponse=True
            )
        except xmlrpc.client.Fault as e:
            result = xmlrpc.client.dumps(e)

        conn.sendall(
            b"Status: 200 OK\r\nContent-Type: text/xml\r\n\r\n"
            + result.encode()
        )

    def close(self) -> None:
        self.sock.close()


class FakeHTTPServer:
    """Keep-alive HTTP server forwarding XML-RPC calls to FakeRTorrent."""

    def __init__(self, backend: FakeRTorrent) -> None:
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # keep connection alive
            # Headers and body are written separately, avoid delayed ACK
            disable_nagle_algorithm = True

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                params, method = xmlrpc.client.loads(body)
                try:
                    result = xmlrpc.client.dumps(
                        (backend.dispatch(method, params),),
                        methodresponse=True,
                    )
                except xmlrpc.client.Fault as e:
                    result = xmlrpc.client.dumps(e)

                data = result.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def backend():
    return FakeRTorrent()


@pytest.fixture
def client(backend):
    server = FakeSCGIServer(backend)
    yield RTorrentClient(host="127.0.0.1", port=str(server.port))
    server.close()


def called(backend: FakeRTorrent, method: str) -> list:
    """Return params of all calls to method (including multicall ones)."""
    return [p for m, p in backend.calls if m == method]


class TestRTorrentClientLifecycle:
    """Test RTorrentClient lifecycle and metadata methods."""

    def test_meta(self, client):
        assert client.meta() == {"name": "rTorrent", "version": "0.9.8"}

    @pytest.mark.parametrize(
        "capability, expected",
        [
            (ClientCapability.CATEGORY, True),
            (ClientCapability.LABEL, True),
            (ClientCapability.SET_PRIORITY, True),
            (ClientCapability.TOGGLE_ALT_SPEED, False),
            (ClientCapability.TORRENT_ID, False),
        ],
    )
    def test_capable(self, client, capability, expected):
        assert client.capable(capability) is expected

    def test_connection_refused(self):
        # Bind and close socket to get port that is surely not listening
        with socket.create_server(("127.0.0.1", 0)) as sock:
            port = sock.getsockname()[1]

        with pytest.raises(ClientError, match="Failed to connect"):
            RTorrentClient(host="127.0.0.1", port=str(port))

    def test_unknown_method(self, client):
        with pytest.raises(RPCFaultError, match="not defined"):
            client._call("d.unknown", HASH)

    def test_empty_response(self):
        """Closed connection without response is reported as ClientError."""
        sock = socket.create_server(("127.0.0.1", 0))

        def serve() -> None:
            conn, _ = sock.accept()
            conn.recv(65536)
            conn.close()

        threading.Thread(target=serve, daemon=True).start()

        with pytest.raises(ClientError, match="without response"):
            RTorrentClient(host="127.0.0.1", port=str(sock.getsockname()[1]))
        sock.close()

    def test_timeout(self, monkeypatch):
        """Hanging daemon is reported as timeout ClientError."""
        monkeypatch.setattr("src.tewi.torrent.clients.rtorrent.TIMEOUT", 0.2)
        sock = socket.create_server(("127.0.0.1", 0))

        with pytest.raises(ClientError, match="Timed out"):
            RTorrentClient(host="127.0.0.1", port=str(sock.getsockname()[1]))
        sock.close()


class TestRTorrentClientHTTP:
    """Test RTorrentClient over HTTP (web server proxy)."""

    @pytest.fixture
    def http_client(self, backend):
        server = FakeHTTPServer(backend)
        yield RTorrentClient(
            host="127.0.0.1", port=str(server.port), path="/RPC2"
        )
        server.close()

    def test_torrents(self, http_client):
        assert [t.name for t in http_client.torrents()] == ["ubuntu"]

    def test_concurrent_calls(self, http_client):
        """Shared HTTP connection is safe to use from several threads."""
        errors = []

        def worker(fn) -> None:
            for _ in range(50):
                try:
                    fn()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(fn,))
            for fn in (
                http_client.torrents,
                lambda: http_client.session([]),
                http_client.preferences,
            )
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


class TestRTorrentClientSession:
    """Test RTorrentClient session and settings methods."""

    def test_session(self, client):
        session = client.session(client.torrents())
        assert session["download_dir"] == "/data/download/"
        assert session["download_dir_free_space"] == 5000
        assert session["upload_speed"] == 5
        assert session["download_speed"] == 10
        assert session["speed_limit_up"] is None
        assert session["speed_limit_down"] == 2048
        assert session["alt_speed_enabled"] is False
        assert session["torrents_count"] == 1
        assert session["torrents_down"] == 1

    def test_session_without_torrents(self, client):
        session = client.session([])
        assert session["download_dir_free_space"] == 0

    def test_stats(self, client):
        stats = client.stats()
        assert stats["current_uploaded_bytes"] == 100
        assert stats["current_downloaded_bytes"] == 400
        assert stats["current_ratio"] == 0.25

    def test_preferences_skip_unknown(self, client):
        prefs = client.preferences()
        assert prefs["network.port_range"] == "50000-50000"
        assert prefs["dht.port"] == "6881"
        assert "system.hostname" not in prefs

    def test_toggle_alt_speed(self, client):
        assert client.toggle_alt_speed() is False


class TestRTorrentClientRetrieval:
    """Test RTorrentClient torrent retrieval methods."""

    def test_torrents(self, client):
        torrents = client.torrents()
        assert len(torrents) == 1

        t = torrents[0]
        assert t.id is None
        assert t.hash == HASH.lower()
        assert t.name == "ubuntu"
        assert t.status == "downloading"
        assert t.total_size == 1000
        assert t.left_until_done == 750
        assert t.percent_done == 0.25
        assert t.eta == timedelta(seconds=75)
        assert t.ratio == 1.5
        assert t.peers_connected == 3
        assert t.peers_getting_from_us == 1
        assert t.peers_sending_to_us == 2
        assert t.priority == 1
        assert t.download_dir == "/data/download"
        assert t.category == "linux iso"
        assert t.labels == ["one", "two"]

    def test_torrent_detail(self, client):
        t = client.torrent(HASH.lower())
        assert t.hash_string == HASH.lower()
        assert t.piece_count == 4
        assert t.piece_size == 256
        assert t.is_private is False
        assert t.comment == "hello world"
        assert t.downloaded_ever == 250
        assert t.error_string is None
        assert t.start_date is not None
        assert t.done_date is None

    def test_torrent_detail_files(self, client):
        files = client.torrent(HASH).files
        assert [f.name for f in files] == ["ubuntu/a.bin", "ubuntu/sub/b.bin"]
        assert files[0].completed == 256
        assert files[0].priority == TorrentFilePriority.MEDIUM
        assert files[1].completed == 400
        assert files[1].priority == TorrentFilePriority.NOT_DOWNLOADING

    def test_torrent_detail_peers(self, client):
        peer = client.torrent(HASH).peers[0]
        assert peer.address == "10.0.0.1"
        assert peer.progress == 0.5
        assert peer.flag_str == "IE"
        assert peer.direction == "Incoming"
        assert peer.dl_state == TorrentPeerState.INTERESTED
        assert peer.ul_state == TorrentPeerState.NONE

    def test_torrent_detail_trackers(self, client):
        tracker, dht = client.torrent(HASH).trackers
        assert tracker.status == "Working"
        assert tracker.seeder_count == 7
        assert tracker.peer_count == 10
        assert tracker.last_announce is not None
        assert dht.status == "Not contacted"
        assert dht.seeder_count is None
        assert dht.last_scrape is None

    def test_torrent_not_found(self, client):
        with pytest.raises(ClientError, match="Could not find"):
            client.torrent("0" * 40)


class TestRTorrentClientOperations:
    """Test RTorrentClient torrent operations."""

    def test_add_magnet(self, client, backend):
        client.add_torrent("magnet:?xt=urn:btih:abc")
        assert backend.loaded == [("load.start", "magnet:?xt=urn:btih:abc")]

    def test_add_hash(self, client, backend):
        client.add_torrent(HASH)
        assert backend.loaded == [("load.start", f"magnet:?xt=urn:btih:{HASH}")]

    def test_add_file(self, client, backend, tmp_path):
        file = tmp_path / "test.torrent"
        file.write_bytes(b"d4:infod4:name4:testee")
        client.add_torrent(str(file))

        method, data = backend.loaded[0]
        assert method == "load.raw_start"
        assert data.data == b"d4:infod4:name4:testee"

    def test_stop_start(self, client):
        client.stop_torrent(HASH)
        assert client.torrents()[0].status == "stopped"

        client.start_torrent([HASH])
        assert client.torrents()[0].status == "downloading"

    def test_stop_start_all(self, client):
        client.stop_all_torrents()
        assert client.torrents()[0].status == "stopped"

        client.start_all_torrents()
        assert client.torrents()[0].status == "downloading"

    def test_verify_reannounce(self, client, backend):
        client.verify_torrent(HASH)
        client.reannounce_torrent([HASH])
        assert called(backend, "d.check_hash") == [[HASH]]
        assert called(backend, "d.tracker_announce") == [[HASH]]

    def test_remove(self, client, backend):
        client.remove_torrent(HASH)
        assert client.torrents() == []
        assert called(backend, "execute.throw") == []

    def test_remove_with_data(self, client, backend):
        client.remove_torrent(HASH, delete_data=True)
        assert client.torrents() == []

        # Data is deleted in background to not block rTorrent
        assert called(backend, "execute.throw") == []
        ((target, shell, flag, script, name, *args),) = called(
            backend, "execute.throw.bg"
        )
        assert (target, shell, flag, name) == ("", "sh", "-c", "sh")
        assert "rm -rf" not in script

        # Only torrent's files, then its directories (deepest first)
        assert args == [
            "/data/download/ubuntu/a.bin",
            "/data/download/ubuntu/sub/b.bin",
            "--",
            "/data/download/ubuntu/sub",
            "/data/download/ubuntu",
        ]

    def test_remove_with_data_unsafe(self, client, backend):
        """Torrent is removed, but unsafe data is kept."""
        backend.torrents[HASH]["files"][1]["f.path"] = "../../etc/passwd"

        client.remove_torrent(HASH, delete_data=True)
        assert client.torrents() == []
        assert called(backend, "execute.throw.bg") == []

    def test_edit_location(self, client, backend):
        client.edit_torrent(HASH, "ubuntu", "/data/moved/")

        (cmd,) = called(backend, "execute.throw")
        assert cmd[-2:] == ("/data/download/ubuntu", "/data/moved")

        t = client.torrents()[0]
        assert t.download_dir == "/data/moved"
        assert t.status == "downloading"

    def test_edit_location_command_failed(self, client, backend):
        """Failed move restarts torrent in previous location."""
        backend.fail_methods.add("execute.throw")

        with pytest.raises(RPCFaultError, match="execute.throw failed"):
            client.edit_torrent(HASH, "ubuntu", "/data/moved")

        t = client.torrents()[0]
        assert t.download_dir == "/data/download"
        assert t.status == "downloading"

    def test_edit_location_unknown_result(self, client, monkeypatch):
        """Move with unknown result (e.g. timeout) leaves torrent stopped."""

        def timeout(*args):
            raise ClientError("Timed out waiting for rTorrent response")

        monkeypatch.setattr(client, "_call_long", timeout)

        with pytest.raises(ClientError, match="left stopped"):
            client.edit_torrent(HASH, "ubuntu", "/data/moved")

        t = client.torrents()[0]
        assert t.download_dir == "/data/download"
        assert t.status == "stopped"

    def test_edit_location_set_directory_failed(self, client, backend):
        """Moved data with old location leaves torrent stopped."""
        backend.fail_methods.add("d.directory.set")

        with pytest.raises(ClientError, match="left stopped"):
            client.edit_torrent(HASH, "ubuntu", "/data/moved")

        assert client.torrents()[0].status == "stopped"

    def test_edit_same_location(self, client, backend):
        client.edit_torrent(HASH, "ubuntu", "/data/download")
        assert called(backend, "execute.throw") == []

    def test_edit_location_conflict(self, client, backend):
        """Existing item with the same name in target is never overwritten."""
        backend.capture_output = "conflict\n"

        with pytest.raises(ClientError, match="already exists"):
            client.edit_torrent(HASH, "ubuntu", "/data/moved")

        # Torrent is untouched: not stopped and not moved
        assert called(backend, "execute.throw") == []
        assert called(backend, "d.stop") == []
        assert client.torrents()[0].download_dir == "/data/download"

    def test_edit_location_relative(self, client, backend):
        with pytest.raises(ClientError, match="absolute path"):
            client.edit_torrent(HASH, "ubuntu", "data/moved")
        assert called(backend, "execute.throw") == []

    def test_edit_rename(self, client):
        with pytest.raises(ClientError, match="renaming"):
            client.edit_torrent(HASH, "new name", "/data/download")


class TestRTorrentClientOrganization:
    """Test RTorrentClient categories, labels and priorities."""

    def test_get_categories(self, client):
        categories = client.get_categories()
        assert [c.name for c in categories] == ["linux iso"]
        assert categories[0].save_path is None

    def test_set_category(self, client):
        client.set_category(HASH, "Movies/HD")
        assert client.torrents()[0].category == "Movies/HD"

        client.set_category([HASH], None)
        assert client.torrents()[0].category is None

    def test_update_labels(self, client):
        client.update_labels(HASH, ["a", "b c"])
        assert client.torrents()[0].labels == ["a", "b c"]

        client.update_labels([HASH], [])
        assert client.torrents()[0].labels == []

    @pytest.mark.parametrize("priority", [-1, 0, 1])
    def test_set_priority(self, client, priority):
        client.set_priority(HASH, priority)
        assert client.torrents()[0].priority == priority

    def test_set_file_priority(self, client, backend):
        client.set_file_priority(HASH, [0, 1], TorrentFilePriority.HIGH)
        files = client.torrent(HASH).files
        assert [f.priority for f in files] == [TorrentFilePriority.HIGH] * 2
        assert called(backend, "d.update_priorities") == [[HASH]]


class TestRTorrentClientHelpers:
    """Test RTorrentClient internal helpers."""

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({}, "downloading"),
            ({"d.complete=": 1}, "seeding"),
            ({"d.state=": 0}, "stopped"),
            ({"d.is_active=": 0}, "stopped"),
            ({"d.hashing=": 1, "d.state=": 0}, "checking"),
        ],
    )
    def test_normalize_status(self, overrides, expected):
        row = {
            "d.hashing=": 0,
            "d.state=": 1,
            "d.is_active=": 1,
            "d.complete=": 0,
        } | overrides
        assert RTorrentClient._normalize_status(row) == expected


class TestRTorrentDeletionPlan:
    """Test selection of files and directories to delete."""

    SESSION = "/data/session/"

    DEFAULT = "/data/dl/"

    def plan(self, directory, multi_file, files, is_meta=0):
        return RTorrentClient._deletion_plan(
            HASH,
            is_meta,
            directory,
            multi_file,
            files,
            self.SESSION,
            self.DEFAULT,
        )

    def test_single_file(self):
        """Download directory of single-file torrent is kept."""
        assert self.plan("/data/dl", 0, [["a.iso", ""]]) == (
            ["/data/dl/a.iso"],
            [],
        )

    def test_frozen_path(self):
        """Absolute path of open torrent is preferred."""
        files = [["a.iso", "/data/dl/a.iso"]]
        assert self.plan("/data/dl/", 0, files) == (["/data/dl/a.iso"], [])

    def test_multi_file(self):
        files = [["x/y/a.bin", ""], ["b.bin", ""], ["x/c.bin", ""]]
        assert self.plan("/data/dl/t", 1, files) == (
            ["/data/dl/t/x/y/a.bin", "/data/dl/t/b.bin", "/data/dl/t/x/c.bin"],
            ["/data/dl/t/x/y", "/data/dl/t/x", "/data/dl/t"],
        )

    def test_multi_file_in_download_dir(self):
        """Download directory is kept even if it's torrent directory."""
        files = [["x/a.bin", ""], ["b.bin", ""]]
        assert self.plan("/data/dl", 1, files) == (
            ["/data/dl/x/a.bin", "/data/dl/b.bin"],
            ["/data/dl/x"],
        )

    def test_meta(self):
        """Magnet placeholder waiting for metadata is kept."""
        assert self.plan("/data/dl", 0, [["H.meta", ""]], is_meta=1) is None

    @pytest.mark.parametrize(
        "directory, multi_file, files",
        [
            # Path traversal
            ("/data/dl/t", 1, [["../other.bin", ""]]),
            ("/data/dl", 0, [["../a.iso", ""]]),
            # Single-file outside of download directory
            ("/data/dl", 0, [["a.iso", "/data/other/a.iso"]]),
            # Frozen path outside of torrent directory
            ("/data/dl/t", 1, [["a.bin", "/data/dl/a.bin"]]),
            # Root and relative directories
            ("/", 1, [["a.bin", ""]]),
            ("relative", 1, [["a.bin", ""]]),
            # Session directory
            ("/data/session", 0, [["H.torrent", ""]]),
            ("/data", 1, [["session/H.torrent", ""]]),
        ],
    )
    def test_unsafe(self, directory, multi_file, files):
        assert self.plan(directory, multi_file, files) is None


class TestRTorrentShellScripts:
    """Test shell scripts executed on rTorrent host with real shell."""

    @staticmethod
    def run(script: str, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", "-c", script, "sh", *[str(a) for a in args]],
            capture_output=True,
            text=True,
        )

    def test_move_file(self, tmp_path):
        (tmp_path / "a.iso").write_text("torrent")
        target = tmp_path / "new" / "dir"

        assert self.run(MOVE_SCRIPT, tmp_path / "a.iso", target).returncode == 0
        assert (target / "a.iso").read_text() == "torrent"
        assert not (tmp_path / "a.iso").exists()

    def test_move_does_not_overwrite_file(self, tmp_path):
        (tmp_path / "a.iso").write_text("torrent")
        (tmp_path / "dst").mkdir()
        (tmp_path / "dst" / "a.iso").write_text("mine")

        result = self.run(MOVE_SCRIPT, tmp_path / "a.iso", tmp_path / "dst")
        assert result.returncode != 0
        assert (tmp_path / "dst" / "a.iso").read_text() == "mine"
        assert (tmp_path / "a.iso").read_text() == "torrent"

    def test_move_does_not_replace_empty_dir(self, tmp_path):
        (tmp_path / "T").mkdir()
        (tmp_path / "T" / "x").write_text("torrent")
        (tmp_path / "dst" / "T").mkdir(parents=True)

        result = self.run(MOVE_SCRIPT, tmp_path / "T", tmp_path / "dst")
        assert result.returncode != 0
        assert (tmp_path / "T" / "x").exists()

    def test_move_missing_source(self, tmp_path):
        """Missing data is skipped, so torrent can be re-pointed."""
        result = self.run(MOVE_SCRIPT, tmp_path / "gone", tmp_path / "dst")
        assert result.returncode == 0
        assert (tmp_path / "dst").is_dir()

    @pytest.mark.parametrize(
        "source, target, expected",
        [
            (True, True, "conflict"),
            (True, False, ""),
            (False, True, ""),
            (False, False, ""),
        ],
    )
    def test_move_conflict(self, tmp_path, source, target, expected):
        if source:
            (tmp_path / "a.iso").write_text("torrent")
        (tmp_path / "dst").mkdir()
        if target:
            (tmp_path / "dst" / "a.iso").write_text("mine")

        result = self.run(
            MOVE_CONFLICT_SCRIPT, tmp_path / "a.iso", tmp_path / "dst" / "a.iso"
        )
        assert result.stdout.strip() == expected

    def test_delete(self, tmp_path):
        root = tmp_path / "T"
        (root / "x" / "y").mkdir(parents=True)
        (root / "x" / "y" / "a.bin").write_text("a")
        (root / "b.bin").write_text("b")
        (root / "x" / "mine.txt").write_text("mine")

        result = self.run(
            DELETE_SCRIPT,
            root / "x" / "y" / "a.bin",
            root / "b.bin",
            "--",
            root / "x" / "y",
            root / "x",
            root,
        )
        assert result.returncode == 0

        # Torrent files and empty directories are removed, others are kept
        remaining = sorted(
            str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")
        )
        assert remaining == ["T", "T/x", "T/x/mine.txt"]
