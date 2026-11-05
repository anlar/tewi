#!/usr/bin/env python3

# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2025  Anton Larionov
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

import threading
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from src.tewi.torrent import util as torrent_util
from src.tewi.torrent.models import ClientError, Torrent
from src.tewi.torrent.util import (
    count_torrents_by_status,
    download_torrent_from_url,
    torrents_test,
)


def create_torrent(
    id=1,
    hash="0" * 40,
    name="test",
    status="downloading",
    size_when_done=1000,
    left_until_done=500,
):
    """Create a test Torrent object with minimal required fields."""
    return Torrent(
        id=id,
        hash=hash,
        name=name,
        status=status,
        total_size=size_when_done,
        size_when_done=size_when_done,
        left_until_done=left_until_done,
        percent_done=0.5,
        eta=timedelta(hours=1),
        rate_upload=1000,
        rate_download=2000,
        ratio=1.5,
        peers_connected=10,
        peers_getting_from_us=5,
        peers_sending_to_us=3,
        uploaded_ever=1500,
        priority=0,
        added_date=datetime.now(),
        activity_date=datetime.now(),
        queue_position=1,
        download_dir="/downloads",
        category=None,
        labels=[],
    )


class TestCountTorrentsByStatus:
    """Test cases for count_torrents_by_status function."""

    def test_empty_list(self):
        """Test counting with empty torrent list."""
        result = count_torrents_by_status([])

        assert result["count"] == 0
        assert result["down"] == 0
        assert result["seed"] == 0
        assert result["check"] == 0
        assert result["stop"] == 0
        assert result["complete_size"] == 0
        assert result["total_size"] == 0

    def test_single_downloading_torrent(self):
        """Test counting with single downloading torrent."""
        torrents = [
            create_torrent(
                id=1,
                status="downloading",
                size_when_done=1000,
                left_until_done=400,
            )
        ]

        result = count_torrents_by_status(torrents)

        assert result["count"] == 1
        assert result["down"] == 1
        assert result["seed"] == 0
        assert result["check"] == 0
        assert result["stop"] == 0
        assert result["complete_size"] == 600  # 1000 - 400
        assert result["total_size"] == 1000

    def test_single_seeding_torrent(self):
        """Test counting with single seeding torrent."""
        torrents = [
            create_torrent(
                id=1,
                status="seeding",
                size_when_done=2000,
                left_until_done=0,
            )
        ]

        result = count_torrents_by_status(torrents)

        assert result["count"] == 1
        assert result["down"] == 0
        assert result["seed"] == 1
        assert result["check"] == 0
        assert result["stop"] == 0
        assert result["complete_size"] == 2000  # 2000 - 0
        assert result["total_size"] == 2000

    def test_single_checking_torrent(self):
        """Test counting with single checking torrent."""
        torrents = [
            create_torrent(
                id=1, status="checking", size_when_done=1500, left_until_done=0
            )
        ]

        result = count_torrents_by_status(torrents)

        assert result["count"] == 1
        assert result["down"] == 0
        assert result["seed"] == 0
        assert result["check"] == 1
        assert result["stop"] == 0
        assert result["complete_size"] == 1500
        assert result["total_size"] == 1500

    def test_single_stopped_torrent(self):
        """Test counting with single stopped torrent."""
        torrents = [
            create_torrent(
                id=1,
                status="stopped",
                size_when_done=3000,
                left_until_done=1000,
            )
        ]

        result = count_torrents_by_status(torrents)

        assert result["count"] == 1
        assert result["down"] == 0
        assert result["seed"] == 0
        assert result["check"] == 0
        assert result["stop"] == 1  # Any status not download/seed/check
        assert result["complete_size"] == 2000  # 3000 - 1000
        assert result["total_size"] == 3000

    def test_mixed_statuses(self):
        """Test counting with torrents in various states."""
        torrents = [
            create_torrent(
                id=1,
                status="downloading",
                size_when_done=1000,
                left_until_done=400,
            ),
            create_torrent(
                id=2,
                status="downloading",
                size_when_done=2000,
                left_until_done=1000,
            ),
            create_torrent(
                id=3, status="seeding", size_when_done=3000, left_until_done=0
            ),
            create_torrent(
                id=4, status="checking", size_when_done=500, left_until_done=0
            ),
            create_torrent(
                id=5,
                status="stopped",
                size_when_done=1500,
                left_until_done=1500,
            ),
            create_torrent(
                id=6, status="paused", size_when_done=800, left_until_done=200
            ),
        ]

        result = count_torrents_by_status(torrents)

        assert result["count"] == 6
        assert result["down"] == 2
        assert result["seed"] == 1
        assert result["check"] == 1
        assert result["stop"] == 2  # stopped + paused
        # complete_size = (1000-400) + (2000-1000) + (3000-0)
        #                 + (500-0) + (1500-1500) + (800-200)
        #               = 600 + 1000 + 3000 + 500 + 0 + 600 = 5700
        assert result["complete_size"] == 5700
        # total_size = 1000 + 2000 + 3000 + 500 + 1500 + 800 = 8800
        assert result["total_size"] == 8800

    def test_size_calculation(self):
        """Test size calculations are correct."""
        torrents = [
            create_torrent(
                id=1,
                status="downloading",
                size_when_done=10000,
                left_until_done=3000,
            ),
            create_torrent(
                id=2,
                status="seeding",
                size_when_done=20000,
                left_until_done=0,
            ),
            create_torrent(
                id=3,
                status="downloading",
                size_when_done=5000,
                left_until_done=5000,
            ),
        ]

        result = count_torrents_by_status(torrents)

        # complete_size = (10000-3000) + (20000-0) + (5000-5000)
        assert result["complete_size"] == 27000
        # total_size = 10000 + 20000 + 5000
        assert result["total_size"] == 35000


class TestTorrentsTest:
    """Test cases for torrents_test function."""

    def test_empty_list_returns_empty(self):
        """Test that empty list returns empty result."""
        result = torrents_test([], 100)
        assert result == []

    def test_multiplies_torrents_to_target_count(self):
        """Test that torrents are multiplied to approximate target count."""
        torrents = [
            create_torrent(id=1, name="torrent1"),
            create_torrent(id=2, name="torrent2"),
        ]

        result = torrents_test(torrents, 5)

        # With 2 torrents and target 5, should create 6 torrents (3x multiplier)
        assert len(result) == 6

    def test_assigns_unique_ids(self):
        """Test that each duplicated torrent gets a unique ID."""
        torrents = [
            create_torrent(id=1, name="torrent1"),
            create_torrent(id=2, name="torrent2"),
        ]

        result = torrents_test(torrents, 5)

        # Check all IDs are unique and sequential
        ids = [t.id for t in result]
        assert ids == [1, 2, 3, 4, 5, 6]

    def test_appends_id_to_name(self):
        """Test that ID is appended to torrent name."""
        torrents = [create_torrent(id=1, name="test")]

        result = torrents_test(torrents, 3)

        # Check names have ID suffix
        assert result[0].name == "test-1"
        assert result[1].name == "test-2"
        assert result[2].name == "test-3"

    def test_preserves_other_fields(self):
        """Test that other torrent fields are preserved."""
        torrents = [
            create_torrent(
                id=1,
                name="original",
                hash="abc123",
                status="seeding",
                size_when_done=5000,
            )
        ]

        result = torrents_test(torrents, 2)

        # Check that fields other than id, name and hash are preserved
        assert result[0].status == "seeding"
        assert result[0].size_when_done == 5000

        assert result[1].status == "seeding"
        assert result[1].size_when_done == 5000

    def test_first_copy_keeps_original_hash(self):
        """Test that first copy of each torrent keeps its original hash."""
        torrents = [
            create_torrent(id=1, name="torrent1", hash="hash1"),
            create_torrent(id=2, name="torrent2", hash="hash2"),
        ]

        result = torrents_test(torrents, 6)

        assert result[0].hash == "hash1"
        assert result[1].hash == "hash2"

    def test_assigns_unique_hashes(self):
        """Test that each duplicated torrent gets a unique hash."""
        torrents = [
            create_torrent(id=1, name="torrent1", hash="hash1"),
            create_torrent(id=2, name="torrent2", hash="hash2"),
        ]

        result = torrents_test(torrents, 100)

        hashes = [t.hash for t in result]
        assert len(set(hashes)) == len(hashes)

    def test_single_torrent_multiplied(self):
        """Test multiplying a single torrent."""
        torrents = [create_torrent(id=1, name="single")]

        result = torrents_test(torrents, 10)

        # Should create 10 copies
        assert len(result) == 10
        # All should have different names
        names = [t.name for t in result]
        assert len(set(names)) == 10


class _TorrentHandler(BaseHTTPRequestHandler):
    """Serve torrent files and redirects for download tests.

    Paths:
        /file          - valid torrent data
        /notorrent     - non-torrent content
        /big           - torrent data over size limit (see fixture)
        /loop          - redirect to itself
        /redirect?to=X - redirect to X (Location header as is)
    """

    TORRENT = b"d8:announce0:4:infod4:name4:testee"

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/file":
            self._send(200, self.TORRENT)
        elif path == "/notorrent":
            self._send(200, b"<html>login</html>")
        elif path == "/big":
            self._send(200, b"d" + b"x" * 2048)
        elif path == "/loop":
            self._redirect("/loop")
        elif path == "/redirect":
            self._redirect(urllib.parse.parse_qs(query)["to"][0])
        else:
            self._send(404, b"")

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    """Run local HTTP server, yield its base URL."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _TorrentHandler)
    thread = threading.Thread(
        target=httpd.serve_forever, args=(0.01,), daemon=True
    )
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def redirect(server: str, to: str) -> str:
    return f"{server}/redirect?{urllib.parse.urlencode({'to': to})}"


class TestDownloadTorrentFromUrl:
    """Test cases for download_torrent_from_url function."""

    MAGNET = "magnet:?xt=urn:btih:" + "a" * 40

    @pytest.mark.parametrize(
        "url", [MAGNET, f"  {MAGNET}\n", MAGNET.replace("magnet", "MAGNET")]
    )
    def test_magnet_link_returned_as_is(self, url):
        assert download_torrent_from_url(url) == (url.strip(), None)

    def test_download_file(self, server):
        result = download_torrent_from_url(f"{server}/file")

        assert result == (None, _TorrentHandler.TORRENT)

    def test_follow_redirect_to_file(self, server):
        result = download_torrent_from_url(redirect(server, "/file"))

        assert result == (None, _TorrentHandler.TORRENT)

    def test_follow_redirect_to_absolute_url(self, server):
        url = redirect(server, f"{server}/file")

        assert download_torrent_from_url(url) == (None, _TorrentHandler.TORRENT)

    def test_redirect_to_magnet(self, server):
        url = redirect(server, self.MAGNET)

        assert download_torrent_from_url(url) == (self.MAGNET, None)

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x.torrent",
            "data:application/x-bittorrent,d4:infoe",
            "/etc/passwd",
            "",
        ],
    )
    def test_unsupported_scheme_rejected(self, url):
        with pytest.raises(ClientError, match="Unsupported"):
            download_torrent_from_url(url)

    @pytest.mark.parametrize(
        "target", ["file:///etc/passwd", "FILE:///etc/passwd", "ftp://x/y"]
    )
    def test_redirect_to_unsupported_scheme_rejected(self, server, target):
        with pytest.raises(ClientError, match="Unsupported"):
            download_torrent_from_url(redirect(server, target))

    def test_redirect_to_local_torrent_file_rejected(self, server, tmp_path):
        local = tmp_path / "secret.torrent"
        local.write_bytes(b"d6:secret4:datae")

        with pytest.raises(ClientError, match="Unsupported"):
            download_torrent_from_url(redirect(server, local.as_uri()))

    def test_redirect_loop_limited(self, server):
        with pytest.raises(ClientError, match="redirects"):
            download_torrent_from_url(f"{server}/loop")

    def test_too_large_file_rejected(self, server, monkeypatch):
        monkeypatch.setattr(torrent_util, "MAX_TORRENT_SIZE", 1024)

        with pytest.raises(ClientError, match="too large"):
            download_torrent_from_url(f"{server}/big")

    def test_not_torrent_rejected(self, server):
        with pytest.raises(ClientError, match="not a valid torrent"):
            download_torrent_from_url(f"{server}/notorrent")

    def test_http_error(self, server):
        with pytest.raises(ClientError, match="404"):
            download_torrent_from_url(f"{server}/missing")
