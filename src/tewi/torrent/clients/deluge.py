"""Deluge torrent client implementation."""

import base64
import os
import urllib.request
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import requests

from ...util.log import log_time
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
from ..util import count_torrents_by_status


class DelugeClient(BaseClient):
    """Deluge client implementation using Web API.

    Documentation: https://deluge.readthedocs.io/en/latest/reference/webapi.html
    Source: https://github.com/deluge-torrent/deluge/blob/develop/deluge/core/core.py
    """

    # Status mapping from Deluge to normalized status
    STATUS_MAP = {
        "Downloading": "downloading",
        "Seeding": "seeding",
        "Paused": "stopped",
        "Checking": "checking",
        "Queued": "stopped",
        "Error": "stopped",
        "Active": "downloading",  # Generic active state
    }

    FIELDS_LIST = [
        "name",
        "hash",
        "state",
        "progress",
        "total_size",
        "total_wanted",
        "total_remaining",
        "download_payload_rate",
        "upload_payload_rate",
        "num_seeds",
        "num_peers",
        "ratio",
        "total_uploaded",
        "priority",
        "time_added",
        "queue",
        "save_path",
        "label",
        "active_time",
        "eta",
        "time_since_transfer",
    ]

    FIELDS_DETAIL = FIELDS_LIST + [
        "num_pieces",
        "piece_length",
        "private",
        "comment",
        "tracker_host",
        "completed_time",
        "total_done",
        "total_uploaded",
        "creator",
        "all_time_download",
        "message",
        "peers",
        "trackers",
        "files",
        "file_priorities",
        "file_progress",
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
        json_path = path or "/json"
        self.base_url = f"http://{host}:{port}{json_path}"
        self._session = requests.Session()
        self.password = password
        self._request_id = 0

        # Authenticate and connect to daemon
        try:
            self._login()
            self._connect_daemon()
        except Exception as e:
            raise ClientError(f"Failed to authenticate with Deluge: {e}")

    def capable(self, capability: ClientCapability) -> bool:
        match capability:
            case ClientCapability.TORRENT_ID:
                return False  # Deluge uses hash strings as IDs
            case ClientCapability.SET_PRIORITY:
                return False
            case ClientCapability.TOGGLE_ALT_SPEED:
                return False
            case ClientCapability.LABEL:
                return False

        return True

    @log_time
    def meta(self) -> ClientMeta:
        """Get daemon name and version."""
        version = self._call("daemon.get_version")
        return {"name": "Deluge", "version": version}

    # ========================================================================
    # Session & Global Settings
    # ========================================================================

    @log_time
    def session(self, torrents: list[Torrent]) -> ClientSession:
        """Get session information with computed torrent counts."""
        # Get config and session status
        config = self._call("core.get_config")
        session_status = self._call(
            "core.get_session_status", [["upload_rate", "download_rate"]]
        )

        # Get free space
        download_dir = config.get("download_location", "")
        free_space = self._call("core.get_free_space", [download_dir])

        counts = count_torrents_by_status(torrents)

        # Deluge doesn't have built-in alt speed mode like Transmission
        # We'll report it as disabled
        alt_speed_enabled = False
        alt_speed_down = 0
        alt_speed_up = 0

        return {
            "download_dir": download_dir,
            "download_dir_free_space": free_space,
            "upload_speed": session_status.get("upload_rate", 0),
            "download_speed": session_status.get("download_rate", 0),
            "alt_speed_enabled": alt_speed_enabled,
            "alt_speed_up": alt_speed_up,
            "alt_speed_down": alt_speed_down,
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
        """Get current and cumulative session statistics."""
        stats = self._call(
            "core.get_session_status",
            [
                [
                    "total_upload",
                    "total_download",
                    "peer.num_peers_connected",
                    "ses.waste_piece_timed_out",
                    "ses.waste_piece_cancelled",
                    "ses.waste_piece_unknown",
                    "ses.waste_piece_seed",
                    "ses.waste_piece_end_game",
                    "ses.waste_piece_closing",
                ]
            ],
        )

        # Deluge tracks session stats only
        current_uploaded = stats.get("total_upload", 0)
        current_downloaded = stats.get("total_download", 0)
        current_ratio = (
            float("inf")
            if current_downloaded == 0
            else current_uploaded / current_downloaded
        )

        current_waste = sum(
            (stats.get(key) or 0)
            for key in stats
            if key.startswith("ses.waste_piece_")
        )

        return {
            "current_uploaded_bytes": current_uploaded,
            "current_downloaded_bytes": current_downloaded,
            "current_ratio": current_ratio,
            "current_active_seconds": None,
            "current_waste": current_waste,
            "current_connected_peers": stats.get("peer.num_peers_connected"),
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
        """Get session preferences as key-value pairs."""
        config = self._call("core.get_config")
        result = {}

        for key, value in config.items():
            if isinstance(value, dict):
                # Flatten nested dictionaries
                flattened = self._flatten_dict(value, key)
                result.update(flattened)
            else:
                # Keep all other types as-is (including lists)
                result[key] = str(value)

        return dict(sorted(result.items()))

    @log_time
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits.

        Note: Deluge doesn't have a built-in alt speed mode.
        """
        return False

    # ========================================================================
    # Torrent Retrieval
    # ========================================================================

    @log_time
    def torrents(self) -> list[Torrent]:
        """Get list of all torrents."""

        torrents_data = self._call(
            "core.get_torrents_status", [{}, self.FIELDS_LIST]
        )

        return [
            self._torrent_to_dto(hash_str, data)
            for hash_str, data in torrents_data.items()
        ]

    @log_time
    def torrent(self, hash: str) -> TorrentDetail:
        """Get detailed information about a specific torrent.

        Reuses _torrent_to_dto for base fields and adds detail-specific
        fields plus files, peers, and trackers.
        """

        torrent_data = self._call(
            "core.get_torrent_status", [hash, self.FIELDS_DETAIL]
        )

        if not torrent_data:
            raise ClientError(f"Torrent with hash {hash} not found")

        # Get base torrent data using _torrent_to_dto
        base_torrent = self._torrent_to_dto(hash, torrent_data)
        base_dict = asdict(base_torrent)

        # Parse files
        files = []
        if torrent_data:
            file_list = torrent_data.get("files", [])
            file_priorities = torrent_data.get("file_priorities", [])
            file_progress = torrent_data.get("file_progress", [])

            for idx, file_info in enumerate(file_list):
                # Get priority and progress for this file
                priority_value = (
                    file_priorities[idx] if idx < len(file_priorities) else 4
                )
                progress = (
                    file_progress[idx] if idx < len(file_progress) else 0.0
                )

                files.append(
                    self._file_to_dto(
                        file_info,
                        index=idx,
                        priority_value=priority_value,
                        progress=progress,
                    )
                )

        # Parse peers
        peers = []
        for p in torrent_data.get("peers", []):
            peers.append(self._peer_to_dto(p))

        # Parse trackers
        trackers = []
        for t in torrent_data.get("trackers", []):
            trackers.append(self._tracker_to_dto(t))

        t = torrent_data

        return TorrentDetail(
            **base_dict,
            hash_string=t.get("hash"),
            piece_count=t.get("num_pieces"),
            piece_size=t.get("piece_length"),
            is_private=t.get("private"),
            comment=t.get("comment"),
            creator=t.get("creator"),
            downloaded_ever=t.get("all_time_download"),
            error_string=(
                t.get("message") if t.get("message") != "OK" else None
            ),
            start_date=None,  # Deluge doesn't provide start date
            done_date=(
                datetime.fromtimestamp(t.get("completed_time"))
                if t.get("completed_time")
                else None
            ),
            files=files,
            peers=peers,
            trackers=trackers,
        )

    # ========================================================================
    # Torrent Lifecycle Operations
    # ========================================================================

    @log_time
    def add_torrent(self, value: str) -> None:
        """Add a torrent from magnet link, HTTP URL, or file path."""
        if value.startswith("magnet:"):
            # Magnet link - use existing method
            self._call("core.add_torrent_magnet", [value, {}])
        elif value.startswith(("http://", "https://")):
            # HTTP/HTTPS URL - download and add as file
            self._add_torrent_from_url(value)
        else:
            # Local file path
            file = os.path.expanduser(value)
            with open(file, "rb") as f:
                file_data = base64.b64encode(f.read()).decode("utf-8")
                self._call("core.add_torrent_file", ["", file_data, {}])

    @log_time
    def start_torrent(self, hashes: str | list[str]) -> None:
        """Start one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self._call("core.resume_torrent", [hashes])

    @log_time
    def start_all_torrents(self) -> None:
        """Start all torrents."""
        torrents_data = self._call("core.get_torrents_status", [{}, ["hash"]])
        torrent_ids = list(torrents_data.keys())
        if torrent_ids:
            self._call("core.resume_torrent", [torrent_ids])

    @log_time
    def stop_torrent(self, hashes: str | list[str]) -> None:
        """Stop one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self._call("core.pause_torrent", [hashes])

    @log_time
    def stop_all_torrents(self) -> None:
        """Stop all torrents."""
        torrents_data = self._call("core.get_torrents_status", [{}, ["hash"]])
        hashes = list(torrents_data.keys())
        if hashes:
            self._call("core.pause_torrent", [hashes])

    @log_time
    def remove_torrent(
        self,
        hashes: str | list[str],
        delete_data: bool = False,
    ) -> None:
        """Remove one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        # Deluge has a batch remove API: core.remove_torrents
        # This is more efficient and handles errors better than
        # calling core.remove_torrent multiple times
        try:
            self._call("core.remove_torrents", [hashes, delete_data])
        except Exception:
            # If batch remove fails, try removing one by one
            # This can happen with older Deluge versions
            for hash_str in hashes:
                try:
                    self._call("core.remove_torrent", [hash_str, delete_data])
                except Exception:
                    # Ignore errors for individual torrents that can't be
                    # removed (e.g., already removed, or protected by plugin)
                    pass

    @log_time
    def verify_torrent(self, hashes: str | list[str]) -> None:
        """Verify one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self._call("core.force_recheck", [hashes])

    @log_time
    def reannounce_torrent(self, hashes: str | list[str]) -> None:
        """Reannounce one or more torrents to their trackers."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self._call("core.force_reannounce", [hashes])

    # ========================================================================
    # Torrent Organization & Metadata
    # ========================================================================

    @log_time
    def edit_torrent(self, hash: str, name: str, location: str) -> None:
        """Edit torrent name and location."""
        torrent = self.torrent(hash)

        if name != torrent.name:
            self._call("core.rename_files", [hash, [[0, name]]])

        if location != torrent.download_dir:
            self._call("core.move_storage", [[hash], location])

    @log_time
    def get_categories(self) -> list[TorrentCategory]:
        """Get list of available torrent categories.

        Note: Deluge uses labels which function as categories.
        Each torrent can have one label selected from a predefined list.
        Labels can have a 'move_completed_path' which is used as save_path.
        """
        try:
            labels = self._call("label.get_labels", [])

            # Get options for each label to retrieve move_completed_path
            categories = []
            for label in labels:
                options = self._call("label.get_options", [label])

                # Use move_completed_path as save_path if it's set
                # Only include path if move_completed is enabled
                save_path = None
                if options.get("apply_move_completed") and options.get(
                    "move_completed_path"
                ):
                    save_path = options["move_completed_path"]

                categories.append(
                    TorrentCategory(name=label, save_path=save_path)
                )

            return categories
        except Exception:
            # If Label plugin is not enabled, return empty list
            return []

    @log_time
    def set_category(
        self, hashes: str | list[str], category: str | None
    ) -> None:
        """Set category for one or more torrents.

        Note: Deluge uses labels which function as categories.
        """

        if isinstance(hashes, str):
            hashes = [hashes]

        try:
            for hash_str in hashes:
                label_value = category if category else ""
                self._call("label.set_torrent", [hash, label_value])
        except Exception:
            # If Label plugin is not enabled, silently fail
            pass

    @log_time
    def update_labels(self, hashes: str | list[str], labels: list[str]) -> None:
        """Update labels/tags for one or more torrents.

        Note: Deluge supports labels that acts like categories.
        """
        pass

    # ========================================================================
    # Priority Management
    # ========================================================================

    @log_time
    def set_priority(self, hashes: str | list[str], priority: int) -> None:
        """Set bandwidth priority for one or more torrents.

        Note: Deluge doesn't support torrent priorities.
        """
        pass

    @log_time
    def set_file_priority(
        self,
        hash: str,
        file_ids: list[int],
        priority: TorrentFilePriority,
    ) -> None:
        """Set download priority for files within a torrent."""
        # Map TorrentFilePriority enum to Deluge priority values
        # Deluge uses 0=Skip, 1=Low, 4=Normal, 7=High
        priority_map = {
            TorrentFilePriority.NOT_DOWNLOADING: 0,
            TorrentFilePriority.LOW: 1,
            TorrentFilePriority.MEDIUM: 4,
            TorrentFilePriority.HIGH: 7,
        }

        deluge_priority = priority_map[priority]

        # Deluge's set_torrent_file_priorities expects a complete list
        # of priorities for all files, so we need to:

        # Get current file priorities
        torrent_data = self._call(
            "core.get_torrent_status", [hash, ["file_priorities"]]
        )
        current_priorities = torrent_data.get("file_priorities", [])

        # Update priorities for specified files
        new_priorities = list(current_priorities)
        for file_id in file_ids:
            if file_id < len(new_priorities):
                new_priorities[file_id] = deluge_priority

        # Set all file priorities
        self._call(
            "core.set_torrent_file_priorities",
            [hash, new_priorities],
        )

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    def _get_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    def _call(self, method: str, params: list[Any] | None = None) -> Any:
        """Make RPC call to Deluge Web API.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            Result from RPC call

        Raises:
            ClientError: If RPC call fails
        """
        if params is None:
            params = []

        data = {
            "method": method,
            "params": params,
            "id": self._get_request_id(),
        }

        try:
            response = self._session.post(self.base_url, json=data)
            response.raise_for_status()
            result = response.json()

            if "error" in result and result["error"]:
                raise ClientError(f"RPC error: {result['error']}")

            return result.get("result")

        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def _login(self) -> None:
        """Login to Deluge Web API."""
        response = self._call("auth.login", [self.password])
        if not response:
            raise ClientError("Login failed")

    def _connect_daemon(self) -> None:
        """Connect to Deluge daemon.

        The Web API requires connecting to a daemon before most
        core/daemon methods are available.
        """
        # Check if already connected
        connected = self._call("web.connected")
        if connected:
            return

        # Get available hosts
        hosts = self._call("web.get_hosts")
        if not hosts or len(hosts) == 0:
            raise ClientError("No Deluge daemon hosts available")

        # Connect to first available host
        host_id = hosts[0][0]  # First element is host ID
        self._call("web.connect", [host_id])

    def _flatten_dict(
        self, data: dict[str, Any], parent_key: str = ""
    ) -> dict[str, str]:
        """Flatten nested dictionary structures into key-value pairs.

        Args:
            data: Dictionary to flatten
            parent_key: Prefix for nested keys

        Returns:
            Flattened dictionary with dot notation for dict keys
        """
        items = []

        for key, value in data.items():
            new_key = f"{parent_key}.{key}" if parent_key else key

            if isinstance(value, dict):
                # Recursively flatten nested dicts
                items.extend(self._flatten_dict(value, new_key).items())
            else:
                # Keep all other types (including lists) as-is
                items.append((new_key, str(value)))

        return dict(items)

    @log_time
    def _normalize_status(self, deluge_status: str) -> str:
        """Normalize Deluge status to common status string."""
        return self.STATUS_MAP.get(deluge_status, "Unknown")

    @log_time
    def _torrent_to_dto(self, hash: str, t: dict[str, Any]) -> Torrent:
        """Convert Deluge torrent data to Torrent.

        Populates list view fields only.
        """

        return Torrent(
            id=None,  # Deluge doesn't use numeric IDs
            hash=hash,
            name=t.get("name"),
            status=self._normalize_status(t.get("state")),
            total_size=t.get("total_size"),
            size_when_done=t.get("total_wanted"),
            left_until_done=t.get("total_remaining"),
            percent_done=t.get("progress") / 100.0,
            eta=timedelta(seconds=t.get("eta")),
            rate_upload=t.get("upload_payload_rate"),
            rate_download=t.get("download_payload_rate"),
            ratio=t.get("ratio"),
            peers_connected=(t.get("num_peers") + t.get("num_seeds")),
            peers_getting_from_us=t.get("num_peers"),
            peers_sending_to_us=t.get("num_seeds"),
            uploaded_ever=t.get("total_uploaded"),
            priority=None,
            added_date=datetime.fromtimestamp(t.get("time_added")),
            activity_date=(
                datetime.now() - timedelta(seconds=t.get("time_since_transfer"))
                if t.get("time_since_transfer") > 0
                else None
            ),
            queue_position=(t.get("queue") if t.get("queue") > -1 else None),
            download_dir=t.get("save_path"),
            category=t.get("label", None),
            labels=[],
        )

    @log_time
    def _file_to_dto(
        self,
        file_data: dict[str, Any],
        index: int | None = None,
        priority_value: int | None = None,
        progress: float | None = None,
    ) -> TorrentFile:
        """Convert Deluge file data to TorrentFile.

        Args:
            file_data: File information dict with 'path', 'size', etc.
            index: File index/ID (uses file_data['index'] if not provided)
            priority_value: File priority value (uses file_data['priority']
                           if not provided)
            progress: File progress 0.0-1.0 (uses file_data['progress']
                     if not provided)
        """
        # Deluge file priorities: 0=Skip, 1=Low, 4=Normal, 7=High
        if priority_value is None:
            priority_value = file_data.get("priority", 4)

        if priority_value == 0:
            priority = TorrentFilePriority.NOT_DOWNLOADING
        elif priority_value == 1:
            priority = TorrentFilePriority.LOW
        elif priority_value <= 4:
            priority = TorrentFilePriority.MEDIUM
        else:
            priority = TorrentFilePriority.HIGH

        size = file_data.get("size", 0)
        if progress is None:
            progress = file_data.get("progress", 0.0)

        if index is None:
            index = file_data.get("index", 0)

        return TorrentFile(
            id=index,
            name=file_data.get("path", "Unknown"),
            size=size,
            completed=int(size * progress),
            priority=priority,
        )

    @log_time
    def _peer_to_dto(self, peer: dict[str, Any]) -> TorrentPeer:
        """Convert Deluge peer data to TorrentPeer."""

        address, port_str = peer.get("ip").split(":", 1)
        port: int = int(port_str)

        return TorrentPeer(
            address=address,
            port=port,
            client_name=peer.get("client"),
            progress=peer.get("progress"),
            is_encrypted=None,
            rate_to_client=peer.get("down_speed"),
            rate_to_peer=peer.get("up_speed"),
            flag_str=None,
            connection_type=None,
            direction=None,
            country=peer.get("country"),
            dl_state=TorrentPeerState.NONE,
            ul_state=TorrentPeerState.NONE,
        )

    @log_time
    def _tracker_to_dto(self, tracker: dict[str, Any]) -> TorrentTracker:
        """Convert Deluge tracker data to TorrentTracker."""

        return TorrentTracker(
            host=tracker.get("url"),
            tier=tracker.get("tier"),
            seeder_count=tracker.get("scrape_complete"),
            leecher_count=tracker.get("scrape_incomplete"),
            download_count=tracker.get("scrape_downloaded"),
            peer_count=None,
            status=None,
            message=tracker.get("message"),
            last_announce=None,
            next_announce=(
                datetime.fromtimestamp(tracker.get("next_announce"))
                if tracker.get("next_announce")
                else None
            ),
            last_scrape=None,
            next_scrape=None,
        )

    def _add_torrent_from_url(self, url: str) -> None:
        """Download torrent file from URL and add to client.

        Args:
            url: HTTP/HTTPS URL to .torrent file

        Raises:
            ClientError: If download or add operation fails
        """

        try:
            # Download torrent file with 30-second timeout
            with urllib.request.urlopen(url, timeout=30) as response:
                if response.status != 200:
                    raise ClientError(
                        f"Failed to download torrent: HTTP {response.status}"
                    )

                torrent_data = response.read()

                # Validate it's actually a torrent file
                # (bencoded, starts with 'd')
                if not torrent_data or torrent_data[0:1] != b"d":
                    raise ClientError(
                        "Downloaded file is not a valid torrent file"
                    )

                # Encode and add to Deluge
                file_data = base64.b64encode(torrent_data).decode("utf-8")
                self._call("core.add_torrent_file", ["", file_data, {}])

        except urllib.error.HTTPError as e:
            raise ClientError(
                f"HTTP error downloading torrent: {e.code} {e.reason}"
            )
        except urllib.error.URLError as e:
            raise ClientError(
                f"Failed to download torrent from {url}: {e.reason}"
            )
        except Exception as e:
            raise ClientError(f"Error adding torrent from URL: {e}")
