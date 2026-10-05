"""rTorrent torrent client implementation."""

import os
import socket
import urllib.parse
import xmlrpc.client
from dataclasses import asdict
from datetime import datetime, timedelta
from http.client import HTTPConnection
from typing import Any

from ...util.log import log_time
from ...util.misc import is_torrent_hash, is_torrent_link
from ..base import BaseClient, ClientCapability
from ..models import (
    ClientError,
    ClientMeta,
    ClientSession,
    ClientStats,
    Torrent,
    TorrentCategory,
    TorrentDetail,
    TorrentFile,
    TorrentFilePriority,
    TorrentPeer,
    TorrentPeerState,
    TorrentTracker,
)
from ..util import count_torrents_by_status, download_torrent_from_url

TIMEOUT = 10  # seconds


class SCGITransport(xmlrpc.client.Transport):
    """XML-RPC transport over SCGI (rTorrent's native RPC protocol).

    Supports TCP connections, host must be passed as "host:port".
    """

    def __init__(self, timeout: float = TIMEOUT) -> None:
        super().__init__()
        self.timeout = timeout

    def single_request(
        self,
        host: str,
        handler: str,
        request_body: bytes,
        verbose: bool = False,
    ) -> tuple[Any, ...]:
        address, _, port = host.rpartition(":")
        headers = b"CONTENT_LENGTH\x00%d\x00SCGI\x001\x00" % len(request_body)
        payload = b"%d:%s,%s" % (len(headers), headers, request_body)

        with socket.create_connection(
            (address, int(port)), timeout=self.timeout
        ) as sock:
            sock.sendall(payload)
            response = b"".join(iter(lambda: sock.recv(65536), b""))

        # Response starts with CGI-style headers, separated from body
        # by an empty line
        _, _, body = response.partition(b"\r\n\r\n")

        parser, unmarshaller = self.getparser()
        parser.feed(body)
        parser.close()
        return unmarshaller.close()


class HTTPTransport(xmlrpc.client.Transport):
    """XML-RPC transport over HTTP with connection timeout."""

    def __init__(self, timeout: float = TIMEOUT) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: Any) -> HTTPConnection:
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn


class HTTPSTransport(xmlrpc.client.SafeTransport):
    """XML-RPC transport over HTTPS with connection timeout."""

    def __init__(self, timeout: float = TIMEOUT) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: Any) -> HTTPConnection:
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn


class RTorrentClient(BaseClient):
    """rTorrent client implementation using XML-RPC.

    Connects either directly to rTorrent SCGI port (when path is not set)
    or via web server proxy (nginx, ruTorrent) exposing XML-RPC over HTTP
    (when path is set, e.g. /RPC2).

    Categories are stored in d.custom1 (ruTorrent label convention),
    labels are stored as comma-separated list in d.custom=tewi_labels.

    Documentation: https://rtorrent-docs.readthedocs.io/en/latest/cmd-ref.html
    """

    LABELS_KEY = "tewi_labels"

    # ruTorrent stores torrent comment in d.custom=comment with this prefix
    COMMENT_PREFIX = "VRS24mrker"

    # rTorrent download priority (0=off, 1=low, 2=normal, 3=high)
    # to normalized bandwidth priority (-1=low, 0=normal, 1=high)
    PRIORITY_MAP = {
        0: -1,
        1: -1,
        2: 0,
        3: 1,
    }

    PRIORITY_MAP_REVERSE = {
        -1: 1,
        0: 2,
        1: 3,
    }

    # rTorrent file priority (0=off, 1=normal, 2=high)
    FILE_PRIORITY_MAP = {
        0: TorrentFilePriority.NOT_DOWNLOADING,
        1: TorrentFilePriority.MEDIUM,
        2: TorrentFilePriority.HIGH,
    }

    # rTorrent has no low file priority, so it's mapped to normal
    FILE_PRIORITY_MAP_REVERSE = {
        TorrentFilePriority.NOT_DOWNLOADING: 0,
        TorrentFilePriority.LOW: 1,
        TorrentFilePriority.MEDIUM: 1,
        TorrentFilePriority.HIGH: 2,
    }

    # Fields requested for torrent list
    FIELDS_LIST = [
        "d.hash=",
        "d.name=",
        "d.state=",
        "d.is_active=",
        "d.complete=",
        "d.hashing=",
        "d.size_bytes=",
        "d.completed_bytes=",
        "d.left_bytes=",
        "d.up.rate=",
        "d.down.rate=",
        "d.ratio=",
        "d.peers_connected=",
        "d.peers_accounted=",
        "d.peers_complete=",
        "d.up.total=",
        "d.priority=",
        "d.load_date=",
        "d.timestamp.started=",
        "d.directory=",
        "d.is_multi_file=",
        "d.custom1=",
        f"d.custom={LABELS_KEY}",
    ]

    # Additional fields requested for torrent details
    FIELDS_DETAIL = FIELDS_LIST + [
        "d.size_chunks=",
        "d.chunk_size=",
        "d.is_private=",
        "d.down.total=",
        "d.message=",
        "d.timestamp.finished=",
        "d.custom=comment",
    ]

    FIELDS_FILE = [
        "f.path=",
        "f.size_bytes=",
        "f.completed_chunks=",
        "f.size_chunks=",
        "f.priority=",
    ]

    FIELDS_PEER = [
        "p.address=",
        "p.port=",
        "p.client_version=",
        "p.completed_percent=",
        "p.is_encrypted=",
        "p.is_obfuscated=",
        "p.is_incoming=",
        "p.is_snubbed=",
        "p.down_rate=",
        "p.up_rate=",
    ]

    FIELDS_TRACKER = [
        "t.url=",
        "t.group=",
        "t.is_enabled=",
        "t.is_busy=",
        "t.scrape_complete=",
        "t.scrape_incomplete=",
        "t.scrape_downloaded=",
        "t.scrape_time_last=",
        "t.latest_sum_peers=",
        "t.success_counter=",
        "t.failed_counter=",
        "t.success_time_last=",
        "t.activity_time_next=",
    ]

    # Global settings displayed in preferences dialog
    PREFERENCES = [
        "directory.default",
        "session.path",
        "network.port_range",
        "network.port_random",
        "network.bind_address",
        "network.local_address",
        "network.max_open_files",
        "network.max_open_sockets",
        "network.http.max_open",
        "network.xmlrpc.size_limit",
        "protocol.pex",
        "dht.port",
        "trackers.use_udp",
        "throttle.global_up.max_rate",
        "throttle.global_down.max_rate",
        "throttle.max_uploads",
        "throttle.max_uploads.global",
        "throttle.max_downloads",
        "throttle.max_downloads.global",
        "throttle.min_peers.normal",
        "throttle.max_peers.normal",
        "throttle.min_peers.seed",
        "throttle.max_peers.seed",
        "pieces.hash.on_completion",
        "pieces.memory.max",
        "pieces.preload.type",
        "system.library_version",
        "system.hostname",
    ]

    # ========================================================================
    # Client Lifecycle & Metadata
    # ========================================================================

    @log_time
    def __init__(
        self,
        host: str,
        port: str,
        path: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        if path:
            scheme = "https" if port == "443" else "http"
            auth = ""
            if username:
                auth = urllib.parse.quote(username, safe="")
                if password:
                    auth += ":" + urllib.parse.quote(password, safe="")
                auth += "@"

            transport = (
                HTTPSTransport() if scheme == "https" else HTTPTransport()
            )
            self.proxy = xmlrpc.client.ServerProxy(
                f"{scheme}://{auth}{host}:{port}{path}",
                transport=transport,
            )
        else:
            self.proxy = xmlrpc.client.ServerProxy(
                f"http://{host}:{port}/",
                transport=SCGITransport(),
            )

        # Check connection
        self.version = self._call("system.client_version")

    @log_time
    def capable(self, capability: ClientCapability) -> bool:
        match capability:
            case ClientCapability.TORRENT_ID:
                return False  # rTorrent uses hash strings as IDs
            case ClientCapability.TOGGLE_ALT_SPEED:
                return False

        return True

    @log_time
    def meta(self) -> ClientMeta:
        return {"name": "rTorrent", "version": self.version}

    # ========================================================================
    # Session & Global Settings
    # ========================================================================

    @log_time
    def session(self, torrents: list[Torrent]) -> ClientSession:
        calls = [
            ("directory.default", ""),
            ("throttle.global_up.rate", ""),
            ("throttle.global_down.rate", ""),
            ("throttle.global_up.max_rate", ""),
            ("throttle.global_down.max_rate", ""),
        ]

        # rTorrent reports free space only for torrent's partition,
        # use first torrent as the closest approximation
        if torrents:
            calls.append(("d.free_diskspace", torrents[0].hash))

        (
            download_dir,
            upload_speed,
            download_speed,
            speed_limit_up,
            speed_limit_down,
            *free_space,
        ) = self._multicall(calls)

        counts = count_torrents_by_status(torrents)

        return {
            "download_dir": download_dir,
            "download_dir_free_space": free_space[0] if free_space else 0,
            "upload_speed": upload_speed,
            "download_speed": download_speed,
            "alt_speed_enabled": False,
            "alt_speed_up": 0,
            "alt_speed_down": 0,
            # 0 means unlimited
            "speed_limit_up": speed_limit_up or None,
            "speed_limit_down": speed_limit_down or None,
            "torrents_complete_size": counts["complete_size"],
            "torrents_total_size": counts["total_size"],
            "torrents_count": counts["count"],
            "torrents_down": counts["down"],
            "torrents_seed": counts["seed"],
            "torrents_check": counts["check"],
            "torrents_stop": counts["stop"],
        }

    @log_time
    def stats(self) -> ClientStats:
        uploaded, downloaded = self._multicall(
            [
                ("throttle.global_up.total", ""),
                ("throttle.global_down.total", ""),
            ]
        )

        return {
            "current_uploaded_bytes": uploaded,
            "current_downloaded_bytes": downloaded,
            "current_ratio": (
                float("inf") if downloaded == 0 else uploaded / downloaded
            ),
            "current_active_seconds": None,
            "current_waste": None,
            "current_connected_peers": None,
            "total_uploaded_bytes": None,
            "total_downloaded_bytes": None,
            "total_ratio": None,
            "total_active_seconds": None,
            "total_started_count": None,
            "cache_read_hits": None,
            "cache_total_buffers_size": None,
            "perf_write_cache_overload": None,
            "perf_read_cache_overload": None,
            "perf_queued_io_jobs": None,
            "perf_average_time_queue": None,
            "perf_total_queued_size": None,
        }

    @log_time
    def preferences(self) -> dict[str, str]:
        calls = [{"methodName": m, "params": [""]} for m in self.PREFERENCES]
        results = self._call("system.multicall", calls)

        # Skip settings not available in current rTorrent version
        return dict(
            sorted(
                (name, str(result[0]))
                for name, result in zip(self.PREFERENCES, results)
                if not isinstance(result, dict)
            )
        )

    @log_time
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits.

        Note: rTorrent doesn't have a built-in alt speed mode.
        """
        return False

    # ========================================================================
    # Torrent Retrieval
    # ========================================================================

    @log_time
    def torrents(self) -> list[Torrent]:
        rows = self._call("d.multicall2", "", "main", *self.FIELDS_LIST)
        return [
            self._torrent_to_dto(dict(zip(self.FIELDS_LIST, r))) for r in rows
        ]

    @log_time
    def torrent(self, hash: str) -> TorrentDetail:
        calls = [self._field_call(f, hash) for f in self.FIELDS_DETAIL]
        calls += [
            ("f.multicall", hash, "", *self.FIELDS_FILE),
            ("p.multicall", hash, "", *self.FIELDS_PEER),
            ("t.multicall", hash, "", *self.FIELDS_TRACKER),
        ]

        *values, files, peers, trackers = self._multicall(calls)
        t = dict(zip(self.FIELDS_DETAIL, values))

        base_torrent = self._torrent_to_dto(t)

        name = t["d.name="]
        chunk_size = t["d.chunk_size="]
        multi_file = bool(t["d.is_multi_file="])

        comment = t["d.custom=comment"]
        if comment.startswith(self.COMMENT_PREFIX):
            comment = urllib.parse.unquote(comment[len(self.COMMENT_PREFIX) :])

        started = t["d.timestamp.started="]
        finished = t["d.timestamp.finished="]

        return TorrentDetail(
            **asdict(base_torrent),
            hash_string=base_torrent.hash,
            piece_count=t["d.size_chunks="],
            piece_size=chunk_size,
            is_private=bool(t["d.is_private="]),
            comment=comment,
            creator="",  # rTorrent doesn't provide creator
            downloaded_ever=t["d.down.total="],
            error_string=t["d.message="] or None,
            start_date=datetime.fromtimestamp(started) if started else None,
            done_date=datetime.fromtimestamp(finished) if finished else None,
            files=[
                self._file_to_dto(
                    idx,
                    dict(zip(self.FIELDS_FILE, f)),
                    name if multi_file else None,
                    chunk_size,
                )
                for idx, f in enumerate(files)
            ],
            peers=[
                self._peer_to_dto(dict(zip(self.FIELDS_PEER, p))) for p in peers
            ],
            trackers=[
                self._tracker_to_dto(dict(zip(self.FIELDS_TRACKER, tr)))
                for tr in trackers
            ],
        )

    # ========================================================================
    # Torrent Lifecycle Operations
    # ========================================================================

    @log_time
    def add_torrent(self, value: str) -> None:
        """Add a torrent from an info hash, magnet link, URL or file.

        A bare v1 info hash (40-char hex or 32-char Base32) is
        converted to a magnet link before being submitted.

        Torrent file content is sent over RPC, so local files can be
        added to remote daemon too.
        """
        if is_torrent_hash(value):
            self._call("load.start", "", f"magnet:?xt=urn:btih:{value.strip()}")
        elif is_torrent_link(value):
            magnet_link, torrent_data = download_torrent_from_url(value)
            if magnet_link:
                self._call("load.start", "", magnet_link)
            else:
                self._load_raw(torrent_data)
        else:
            file = os.path.expanduser(value)
            with open(file, "rb") as f:
                self._load_raw(f.read())

    @log_time
    def start_torrent(self, hashes: str | list[str]) -> None:
        # d.start starts stopped torrent, d.resume resumes paused one;
        # both are no-op for already running torrents
        self._multicall(
            [
                call
                for h in self._to_list(hashes)
                for call in (("d.start", h), ("d.resume", h))
            ]
        )

    @log_time
    def start_all_torrents(self) -> None:
        self.start_torrent(self._all_hashes())

    @log_time
    def stop_torrent(self, hashes: str | list[str]) -> None:
        self._multicall(
            [
                call
                for h in self._to_list(hashes)
                for call in (("d.stop", h), ("d.close", h))
            ]
        )

    @log_time
    def stop_all_torrents(self) -> None:
        self.stop_torrent(self._all_hashes())

    @log_time
    def remove_torrent(
        self,
        hashes: str | list[str],
        delete_data: bool = False,
    ) -> None:
        hashes = self._to_list(hashes)

        # Data paths should be resolved before torrent is erased
        paths = self._data_paths(hashes) if delete_data else []

        self._multicall([("d.erase", h) for h in hashes])

        if paths:
            default_dir = self._call("directory.default")
            for path in paths:
                if self._is_safe_to_delete(path, default_dir):
                    self._call("execute.throw", "", "rm", "-rf", "--", path)

    @log_time
    def verify_torrent(self, hashes: str | list[str]) -> None:
        self._multicall([("d.check_hash", h) for h in self._to_list(hashes)])

    @log_time
    def reannounce_torrent(self, hashes: str | list[str]) -> None:
        self._multicall(
            [("d.tracker_announce", h) for h in self._to_list(hashes)]
        )

    # ========================================================================
    # Torrent Organization & Metadata
    # ========================================================================

    @log_time
    def edit_torrent(self, hash: str, name: str, location: str) -> None:
        """Edit torrent download location.

        Note: rTorrent doesn't support renaming torrents.

        Data is moved by rTorrent itself, torrent is stopped during move
        and restarted afterwards if it was running.
        """
        current_name, directory, multi_file, state = self._multicall(
            [
                ("d.name", hash),
                ("d.directory", hash),
                ("d.is_multi_file", hash),
                ("d.state", hash),
            ]
        )

        if name != current_name:
            raise ClientError("rTorrent doesn't support renaming torrents")

        # Path is resolved on rTorrent host, so ~ isn't expanded here
        location = os.path.normpath(location)
        current_location = (
            os.path.dirname(directory) if multi_file else directory
        )
        if location == os.path.normpath(current_location):
            return

        source = self._data_path(directory, current_name, multi_file)

        self.stop_torrent(hash)
        try:
            self._call(
                "execute.throw",
                "",
                "sh",
                "-c",
                'mkdir -p -- "$2" && if [ -e "$1" ]; then mv -- "$1" "$2"/; fi',
                "sh",
                source,
                location,
            )
            # For multi-file torrents rTorrent appends torrent name
            # to the directory
            self._call("d.directory.set", hash, location)
        finally:
            if state:
                self.start_torrent(hash)

    @log_time
    def get_categories(self) -> list[TorrentCategory]:
        """Get list of categories used by torrents.

        Note: rTorrent has no category registry, so list is collected
        from labels (ruTorrent convention) assigned to existing torrents.
        """
        rows = self._call("d.multicall2", "", "main", "d.custom1=")
        names = {urllib.parse.unquote(r[0]) for r in rows if r[0]}
        return [TorrentCategory(name=n, save_path=None) for n in sorted(names)]

    @log_time
    def set_category(
        self, hashes: str | list[str], category: str | None
    ) -> None:
        value = urllib.parse.quote(category, safe="") if category else ""
        self._multicall(
            [("d.custom1.set", h, value) for h in self._to_list(hashes)]
        )

    @log_time
    def update_labels(self, hashes: str | list[str], labels: list[str]) -> None:
        value = ",".join(labels)
        self._multicall(
            [
                ("d.custom.set", h, self.LABELS_KEY, value)
                for h in self._to_list(hashes)
            ]
        )

    # ========================================================================
    # Priority Management
    # ========================================================================

    @log_time
    def set_priority(self, hashes: str | list[str], priority: int) -> None:
        """Set bandwidth priority for one or more torrents."""
        value = self.PRIORITY_MAP_REVERSE[priority]
        self._multicall(
            [
                call
                for h in self._to_list(hashes)
                for call in (
                    ("d.priority.set", h, value),
                    ("d.update_priorities", h),
                )
            ]
        )

    @log_time
    def set_file_priority(
        self,
        hash: str,
        file_ids: list[int],
        priority: TorrentFilePriority,
    ) -> None:
        """Set download priority for files within a torrent.

        Note: rTorrent has no low file priority, it's set as normal.
        """
        value = self.FILE_PRIORITY_MAP_REVERSE[priority]
        calls = [("f.priority.set", f"{hash}:f{i}", value) for i in file_ids]
        calls.append(("d.update_priorities", hash))
        self._multicall(calls)

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    def _call(self, method: str, *params: Any) -> Any:
        """Call rTorrent RPC method and wrap errors into ClientError."""
        try:
            return getattr(self.proxy, method)(*params)
        except xmlrpc.client.Fault as e:
            raise ClientError(f"RPC error: {e.faultString}")
        except xmlrpc.client.ProtocolError as e:
            raise ClientError(f"HTTP error: {e.errcode} {e.errmsg}")
        except (OSError, xmlrpc.client.Error) as e:
            raise ClientError(f"Failed to connect to rTorrent: {e}")

    def _multicall(self, calls: list[tuple[Any, ...]]) -> list[Any]:
        """Execute several methods in single request.

        Args:
            calls: List of tuples (method, *params)

        Returns:
            List of results in the same order as calls
        """
        if not calls:
            return []

        results = self._call(
            "system.multicall",
            [{"methodName": m, "params": list(p)} for m, *p in calls],
        )

        values = []
        for result in results:
            if isinstance(result, dict):
                raise ClientError(f"RPC error: {result.get('faultString')}")
            values.append(result[0])
        return values

    def _load_raw(self, data: bytes) -> None:
        """Add torrent from .torrent file content."""
        self._call("load.raw_start", "", xmlrpc.client.Binary(data))

    def _all_hashes(self) -> list[str]:
        return self._call("download_list", "")

    def _data_paths(self, hashes: list[str]) -> list[str]:
        """Get paths to downloaded data for torrents."""
        calls = [
            call
            for h in hashes
            for call in (
                ("d.directory", h),
                ("d.name", h),
                ("d.is_multi_file", h),
            )
        ]
        values = self._multicall(calls)
        return [
            self._data_path(*values[i : i + 3])
            for i in range(0, len(values), 3)
        ]

    @staticmethod
    def _to_list(hashes: str | list[str]) -> list[str]:
        return [hashes] if isinstance(hashes, str) else list(hashes)

    @staticmethod
    def _field_call(field: str, hash: str) -> tuple[Any, ...]:
        """Convert multicall field (e.g. "d.custom=key") to method call."""
        method, _, arg = field.partition("=")
        return (method, hash, arg) if arg else (method, hash)

    @staticmethod
    def _data_path(directory: str, name: str, multi_file: int) -> str:
        """Get path to torrent data.

        Note: d.base_path can't be used as it's empty for closed torrents.
        """
        if multi_file:
            return directory
        return os.path.join(directory, name)

    @staticmethod
    def _is_safe_to_delete(path: str, default_dir: str) -> bool:
        """Check that path looks like torrent data and not a top directory."""
        if os.path.basename(path.rstrip(os.sep)) in ("", ".", ".."):
            return False

        path = os.path.normpath(path)
        return (
            os.path.isabs(path)
            and path.count(os.sep) > 1
            and path != os.path.normpath(default_dir)
        )

    @staticmethod
    def _normalize_status(t: dict[str, Any]) -> str:
        """Derive common status string from rTorrent state flags."""
        if t["d.hashing="]:
            return "checking"
        if not t["d.state="] or not t["d.is_active="]:
            return "stopped"
        if t["d.complete="]:
            return "seeding"
        return "downloading"

    @staticmethod
    def _ts_to_dt(timestamp: int) -> datetime | None:
        """Convert Unix timestamp to datetime (None for unset values)."""
        return datetime.fromtimestamp(timestamp) if timestamp > 0 else None

    @log_time
    def _torrent_to_dto(self, t: dict[str, Any]) -> Torrent:
        """Convert rTorrent fields to Torrent.

        Populates list view fields only.
        """
        size = t["d.size_bytes="]
        left = t["d.left_bytes="]
        rate_download = t["d.down.rate="]

        eta = None
        if rate_download > 0 and left > 0:
            eta = timedelta(seconds=left // rate_download)

        added_date = datetime.fromtimestamp(t["d.load_date="])
        started = t["d.timestamp.started="]

        # d.directory points to torrent content directory
        # for multi-file torrents
        download_dir = t["d.directory="]
        if t["d.is_multi_file="]:
            download_dir = os.path.dirname(download_dir)

        labels = t[f"d.custom={self.LABELS_KEY}"]

        return Torrent(
            id=None,  # rTorrent doesn't use numeric IDs
            hash=t["d.hash="].lower(),
            name=t["d.name="],
            status=self._normalize_status(t),
            total_size=size,
            size_when_done=size,
            left_until_done=left,
            percent_done=t["d.completed_bytes="] / size if size else 0.0,
            eta=eta,
            rate_upload=t["d.up.rate="],
            rate_download=rate_download,
            # rTorrent returns ratio multiplied by 1000
            ratio=t["d.ratio="] / 1000,
            peers_connected=t["d.peers_connected="],
            peers_getting_from_us=t["d.peers_accounted="],
            peers_sending_to_us=t["d.peers_complete="],
            uploaded_ever=t["d.up.total="],
            priority=self.PRIORITY_MAP.get(t["d.priority="], 0),
            added_date=added_date,
            # rTorrent doesn't track last activity time,
            # use start time as the closest approximation
            activity_date=(
                datetime.fromtimestamp(started) if started else added_date
            ),
            queue_position=None,
            download_dir=download_dir,
            # ruTorrent convention: label is stored in custom1
            category=urllib.parse.unquote(t["d.custom1="]) or None,
            labels=[x for x in labels.split(",") if x],
        )

    @log_time
    def _file_to_dto(
        self,
        idx: int,
        f: dict[str, Any],
        root: str | None,
        chunk_size: int,
    ) -> TorrentFile:
        """Convert rTorrent file fields to TorrentFile.

        Completed size is calculated from completed chunks, so it's
        approximate for files sharing chunks with neighbours.
        """
        size = f["f.size_bytes="]
        if f["f.completed_chunks="] >= f["f.size_chunks="]:
            completed = size
        else:
            completed = min(size, f["f.completed_chunks="] * chunk_size)

        # Include torrent directory to match other clients
        name = f"{root}/{f['f.path=']}" if root else f["f.path="]

        return TorrentFile(
            id=idx,
            name=name,
            size=size,
            completed=completed,
            priority=self.FILE_PRIORITY_MAP.get(
                f["f.priority="], TorrentFilePriority.MEDIUM
            ),
        )

    @log_time
    def _peer_to_dto(self, p: dict[str, Any]) -> TorrentPeer:
        """Convert rTorrent peer fields to TorrentPeer.

        Note: rTorrent doesn't expose choke/interest flags, so peer states
        are derived from transfer rates and snubbed flag.
        """
        flags = ""
        if p["p.is_incoming="]:
            flags += "I"
        if p["p.is_encrypted="]:
            flags += "E"
        elif p["p.is_obfuscated="]:
            flags += "e"
        if p["p.is_snubbed="]:
            flags += "S"

        if p["p.down_rate="] > 0:
            dl_state = TorrentPeerState.INTERESTED
        elif p["p.is_snubbed="]:
            dl_state = TorrentPeerState.CHOKED
        else:
            dl_state = TorrentPeerState.NONE

        if p["p.up_rate="] > 0:
            ul_state = TorrentPeerState.INTERESTED
        else:
            ul_state = TorrentPeerState.NONE

        return TorrentPeer(
            address=p["p.address="],
            client_name=p["p.client_version="],
            progress=p["p.completed_percent="] / 100,
            is_encrypted=bool(p["p.is_encrypted="]),
            rate_to_client=p["p.down_rate="],
            rate_to_peer=p["p.up_rate="],
            flag_str=flags,
            port=p["p.port="],
            connection_type="TCP",  # rTorrent supports TCP only
            direction="Incoming" if p["p.is_incoming="] else "Outgoing",
            country=None,
            dl_state=dl_state,
            ul_state=ul_state,
        )

    @log_time
    def _tracker_to_dto(self, t: dict[str, Any]) -> TorrentTracker:
        """Convert rTorrent tracker fields to TorrentTracker.

        Note: success counter is reset when torrent restarts, so last
        success time is used to detect working trackers too.
        """
        announced = t["t.success_counter="] > 0 or t["t.success_time_last="] > 0

        if not t["t.is_enabled="]:
            status = "Disabled"
        elif t["t.is_busy="]:
            status = "Updating"
        elif t["t.failed_counter="] > 0:
            status = "Not working"
        elif announced:
            status = "Working"
        else:
            status = "Not contacted"

        # Scrape counters are meaningless until first scrape
        scraped = t["t.scrape_time_last="] > 0

        return TorrentTracker(
            host=t["t.url="],
            tier=t["t.group="],
            seeder_count=t["t.scrape_complete="] if scraped else None,
            leecher_count=t["t.scrape_incomplete="] if scraped else None,
            download_count=t["t.scrape_downloaded="] if scraped else None,
            status=status,
            message="",  # rTorrent doesn't provide per-tracker messages
            peer_count=t["t.latest_sum_peers="] if announced else None,
            last_announce=self._ts_to_dt(t["t.success_time_last="]),
            next_announce=self._ts_to_dt(t["t.activity_time_next="]),
            last_scrape=self._ts_to_dt(t["t.scrape_time_last="]),
            next_scrape=None,
        )
