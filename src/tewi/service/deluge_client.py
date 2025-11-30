"""Deluge torrent client implementation."""

import os
from datetime import datetime, timedelta
from typing import Any

import requests

from ..util.misc import is_torrent_link
from ..util.decorator import log_time
from ..common import (CategoryDTO, FilterOption, SortOrder, TorrentDTO,
                      TorrentDetailDTO, FileDTO, PeerDTO, TrackerDTO,
                      PeerState, FilePriority)
from .base_client import (BaseClient, ClientMeta, ClientStats,
                          ClientSession, ClientError)


class DelugeClient(BaseClient):
    """Deluge client implementation using Web API."""

    # Status mapping from Deluge to normalized status
    STATUS_MAP = {
        'Downloading': 'downloading',
        'Seeding': 'seeding',
        'Paused': 'stopped',
        'Checking': 'checking',
        'Queued': 'stopped',
        'Error': 'stopped',
        'Active': 'downloading',  # Generic active state
    }

    FIELDS_LIST = [
            "name", "hash", "state", "progress", "total_size", "total_wanted",
            "total_remaining", "download_payload_rate",
            "upload_payload_rate", "num_seeds", "num_peers", "ratio",
            "total_uploaded", "priority", "time_added", "queue",
            "save_path", "label", "active_time"
        ]

    FIELDS_DETAIL = FIELDS_LIST + [
            "num_pieces", "piece_length",
            "private", "comment", "tracker_host",
            "total_done", "total_uploaded",
            "message", "peers", "trackers",
            "files", "file_priorities","file_progress"
        ]

    @log_time
    def __init__(self,
                 host: str, port: str,
                 username: str = None, password: str = None):

        self.base_url = f"http://{host}:{port}/json"
        self._session = requests.Session()
        self.password = password or "deluge"
        self._request_id = 0

        # Authenticate and connect to daemon
        try:
            self._login()
            self._connect_daemon()
        except Exception as e:
            raise ClientError(f"Failed to authenticate with Deluge: {e}")

    def _get_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

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

    def _call(self, method: str, params: list = None) -> Any:
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
            "id": self._get_request_id()
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

    def capable(self, capability_code: str) -> bool:
        match capability_code:
            case 'torrent_id':
                return False  # Deluge uses hash strings as IDs
            case 'category':
                return False  # Deluge doesn't support categories
            case 'set_priority':
                return True

        return True

    @log_time
    def meta(self) -> ClientMeta:
        """Get daemon name and version."""
        version = self._call("daemon.get_version")
        return {
            'name': 'Deluge',
            'version': version
        }

    @log_time
    def stats(self) -> ClientStats:
        """Get current and cumulative session statistics."""
        stats = self._call("core.get_session_status", [
            ["upload_rate", "download_rate", "total_upload",
             "total_download", "num_connections"]
        ])

        # Deluge tracks all-time stats but not per-session stats separately
        total_uploaded = stats.get("total_upload", 0)
        total_downloaded = stats.get("total_download", 0)
        total_ratio = (
            float('inf')
            if total_downloaded == 0
            else total_uploaded / total_downloaded
        )

        return {
            'current_uploaded_bytes': None,
            'current_downloaded_bytes': None,
            'current_ratio': None,
            'current_active_seconds': None,
            'current_waste': None,
            'current_connected_peers': stats.get("num_connections"),
            'total_uploaded_bytes': total_uploaded,
            'total_downloaded_bytes': total_downloaded,
            'total_ratio': total_ratio,
            'total_active_seconds': None,
            'total_started_count': None,
            'cache_read_hits': None,
            'cache_total_buffers_size': None,
            'perf_write_cache_overload': None,
            'perf_read_cache_overload': None,
            'perf_queued_io_jobs': None,
            'perf_average_time_queue': None,
            'perf_total_queued_size': None,
        }

    @log_time
    def session(self, torrents: list[TorrentDTO], sort_order: SortOrder,
                sort_order_asc: bool,
                filter_option: FilterOption) -> ClientSession:
        """Get session information with computed torrent counts."""
        # Get config and session status
        config = self._call("core.get_config")
        session_status = self._call("core.get_session_status", [
            ["upload_rate", "download_rate"]
        ])

        # Get free space
        download_dir = config.get("download_location", "")
        try:
            free_space = self._call("core.get_free_space", [download_dir])
        except Exception:
            free_space = 0

        torrents_count = len(torrents)
        torrents_down = 0
        torrents_seed = 0
        torrents_check = 0
        torrents_complete_size = 0
        torrents_total_size = 0

        for t in torrents:
            torrents_total_size += t.size_when_done
            torrents_complete_size += t.size_when_done - t.left_until_done

            if t.status == 'downloading':
                torrents_down += 1
            elif t.status == 'seeding':
                torrents_seed += 1
            elif t.status == 'checking':
                torrents_check += 1

        torrents_stop = (torrents_count - torrents_down - torrents_seed -
                         torrents_check)

        # Deluge doesn't have built-in alt speed mode like Transmission
        # We'll report it as disabled
        alt_speed_enabled = False
        alt_speed_down = 0
        alt_speed_up = 0

        return {
            'download_dir': download_dir,
            'download_dir_free_space': free_space,
            'upload_speed': session_status.get("upload_rate", 0),
            'download_speed': session_status.get("download_rate", 0),
            'alt_speed_enabled': alt_speed_enabled,
            'alt_speed_up': alt_speed_up,
            'alt_speed_down': alt_speed_down,
            'torrents_complete_size': torrents_complete_size,
            'torrents_total_size': torrents_total_size,
            'torrents_count': torrents_count,
            'torrents_down': torrents_down,
            'torrents_seed': torrents_seed,
            'torrents_check': torrents_check,
            'torrents_stop': torrents_stop,
            'sort_order': sort_order,
            'sort_order_asc': sort_order_asc,
            'filter_option': filter_option,
        }

    @log_time
    def preferences(self) -> dict[str, str]:
        """Get session preferences as key-value pairs."""
        config = self._call("core.get_config")
        return {k: str(v) for k, v in sorted(config.items())}

    @log_time
    def _normalize_status(self, deluge_status: str) -> str:
        """Normalize Deluge status to common status string."""
        return self.STATUS_MAP.get(deluge_status, 'stopped')

    @log_time
    def _torrent_to_dto(self, torrent_hash: str, torrent_data: dict
                        ) -> TorrentDTO:
        """Convert Deluge torrent data to TorrentDTO."""
        # Calculate ETA
        download_rate = torrent_data.get("download_payload_rate", 0)
        total_remaining = torrent_data.get("total_remaining", 0)

        if download_rate > 0 and total_remaining > 0:
            eta_seconds = total_remaining / download_rate
            eta = timedelta(seconds=int(eta_seconds))
        else:
            eta = timedelta(seconds=-1)

        # Deluge doesn't provide activity_date, use time_added
        time_added = torrent_data.get("time_added", 0)
        added_date = (datetime.fromtimestamp(time_added) if time_added > 0
                      else datetime.now())

        return TorrentDTO(
            id=torrent_hash,
            name=torrent_data.get("name", "Unknown"),
            status=self._normalize_status(
                torrent_data.get("state", "Unknown")),
            total_size=torrent_data.get("total_size", 0),
            size_when_done=torrent_data.get("total_wanted", 0),
            left_until_done=torrent_data.get("total_remaining", 0),
            percent_done=torrent_data.get("progress", 0) / 100.0,
            eta=eta,
            rate_upload=torrent_data.get("upload_payload_rate", 0),
            rate_download=torrent_data.get("download_payload_rate", 0),
            ratio=torrent_data.get("ratio", 0.0),
            peers_connected=(torrent_data.get("num_peers", 0) +
                             torrent_data.get("num_seeds", 0)),
            peers_getting_from_us=torrent_data.get("num_peers", 0),
            peers_sending_to_us=torrent_data.get("num_seeds", 0),
            uploaded_ever=torrent_data.get("total_uploaded", 0),
            priority=torrent_data.get("priority", 0),
            added_date=added_date,
            activity_date=added_date,  # Use added_date as fallback
            queue_position=(
                torrent_data.get("queue")
                if torrent_data.get("queue") > -1
                else None
                ),
            download_dir=torrent_data.get("save_path", ""),
            category=None,  # Deluge doesn't support categories
            labels=(list(torrent_data.get("label", []))
                    if torrent_data.get("label") else []),
        )

    @log_time
    def torrents(self) -> list[TorrentDTO]:
        """Get list of all torrents."""
        # Define fields to retrieve
        torrents_data = self._call("core.get_torrents_status",
                                   [{}, self.FIELDS_LIST])

        if not torrents_data:
            return []

        return [self._torrent_to_dto(hash_str, data)
                for hash_str, data in torrents_data.items()]

    @log_time
    def _file_to_dto(self, file_data: dict) -> FileDTO:
        """Convert Deluge file data to FileDTO."""
        # Deluge file priorities: 0=Skip, 1=Low, 4=Normal, 7=High
        priority_value = file_data.get("priority", 4)

        if priority_value == 0:
            priority = FilePriority.NOT_DOWNLOADING
        elif priority_value == 1:
            priority = FilePriority.LOW
        elif priority_value <= 4:
            priority = FilePriority.MEDIUM
        else:
            priority = FilePriority.HIGH

        size = file_data.get("size", 0)
        progress = file_data.get("progress", 0.0)

        return FileDTO(
            id=file_data.get("index", 0),
            name=file_data.get("path", "Unknown"),
            size=size,
            completed=int(size * progress),
            priority=priority,
        )

    @log_time
    def _peer_to_dto(self, peer: dict) -> PeerDTO:
        """Convert Deluge peer data to PeerDTO."""

        address, port = peer.get("ip").split(":", 1)

        return PeerDTO(
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
            country=peer.get("country", None),
            dl_state=PeerState.NONE,
            ul_state=PeerState.NONE,
        )

    @log_time
    def _tracker_to_dto(self, tracker: dict) -> TrackerDTO:
        """Convert Deluge tracker data to TrackerDTO."""

        return TrackerDTO(
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

    @log_time
    def torrent(self, id: int | str) -> TorrentDetailDTO:
        """Get detailed information about a specific torrent."""
        # Get torrent status
        torrent_data = self._call("core.get_torrent_status",
                                  [id, self.FIELDS_DETAIL])

        if not torrent_data:
            raise ClientError(f"Torrent with ID {id} not found")

        files = []
        if torrent_data:
            file_list = torrent_data.get("files", [])
            file_priorities = torrent_data.get("file_priorities", [])
            file_progress = torrent_data.get("file_progress", [])

            for idx, file_info in enumerate(file_list):
                # Get priority for this file (default to 1/normal if not available)
                priority_value = (file_priorities[idx]
                                  if idx < len(file_priorities) else 1)

                # Map Deluge file priorities to FilePriority enum
                # Deluge uses 0=Skip, 1=Low, 4=Normal, 7=High
                if priority_value == 0:
                    priority = FilePriority.NOT_DOWNLOADING
                elif priority_value == 1:
                    priority = FilePriority.LOW
                elif priority_value <= 4:
                    priority = FilePriority.MEDIUM
                else:
                    priority = FilePriority.HIGH

                size = file_info.get("size", 0)
                progress = (file_progress[idx]
                            if idx < len(file_progress) else 0.0)

                files.append(FileDTO(
                    id=idx,
                    name=file_info.get("path", "Unknown"),
                    size=size,
                    completed=int(size * progress),
                    priority=priority,
                ))

        # Get peers - Deluge web API doesn't easily expose peer list
        peers = []
        for p in torrent_data.get("peers", []):
            peers.append(self._peer_to_dto(p))

        # Get trackers
        tracker_data = self._call("core.get_torrent_status",
                                  [id, ["trackers"]])
        trackers = []
        if tracker_data and "trackers" in tracker_data:
            for t in tracker_data["trackers"]:
                trackers.append(self._tracker_to_dto(t))

        time_added = torrent_data.get("time_added", 0)
        added_date = (datetime.fromtimestamp(time_added) if time_added > 0
                      else datetime.now())

        return TorrentDetailDTO(
            id=id,
            name=torrent_data.get("name", "Unknown"),
            hash_string=torrent_data.get("hash", str(id)),
            total_size=torrent_data.get("total_size", 0),
            piece_count=torrent_data.get("num_pieces", 0),
            piece_size=torrent_data.get("piece_length", 0),
            is_private=torrent_data.get("private", False),
            comment=torrent_data.get("comment", ""),
            creator="",  # Not provided by Deluge
            labels=(list(torrent_data.get("label", []))
                    if torrent_data.get("label") else []),
            category=None,
            status=self._normalize_status(
                torrent_data.get("state", "Unknown")),
            download_dir=torrent_data.get("save_path", ""),
            downloaded_ever=torrent_data.get("total_done", 0),
            uploaded_ever=torrent_data.get("total_uploaded", 0),
            ratio=torrent_data.get("ratio", 0.0),
            error_string=torrent_data.get("message", ""),
            added_date=added_date,
            start_date=added_date,  # Deluge doesn't distinguish
            done_date=added_date,  # Deluge doesn't provide
            activity_date=added_date,
            peers_connected=(torrent_data.get("num_peers", 0) +
                             torrent_data.get("num_seeds", 0)),
            peers_sending_to_us=torrent_data.get("num_seeds", 0),
            peers_getting_from_us=torrent_data.get("num_peers", 0),
            files=files,
            peers=peers,
            trackers=trackers,
        )

    @log_time
    def add_torrent(self, value: str) -> None:
        """Add a torrent from magnet link or file path."""
        if is_torrent_link(value):
            self._call("core.add_torrent_magnet", [value, {}])
        else:
            file = os.path.expanduser(value)
            with open(file, 'rb') as f:
                import base64
                file_data = base64.b64encode(f.read()).decode('utf-8')
                self._call("core.add_torrent_file", ["", file_data, {}])

    @log_time
    def start_torrent(self, torrent_ids: int | str | list[int | str]
                      ) -> None:
        """Start one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        for torrent_id in torrent_ids:
            self._call("core.resume_torrent", [[str(torrent_id)]])

    @log_time
    def stop_torrent(self, torrent_ids: int | str | list[int | str]
                     ) -> None:
        """Stop one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        for torrent_id in torrent_ids:
            self._call("core.pause_torrent", [[str(torrent_id)]])

    @log_time
    def remove_torrent(self, torrent_ids: int | str | list[int | str],
                       delete_data: bool = False) -> None:
        """Remove one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        for torrent_id in torrent_ids:
            self._call("core.remove_torrent", [str(torrent_id), delete_data])

    @log_time
    def verify_torrent(self, torrent_ids: int | str | list[int | str]
                       ) -> None:
        """Verify one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        for torrent_id in torrent_ids:
            self._call("core.force_recheck", [[str(torrent_id)]])

    @log_time
    def reannounce_torrent(self, torrent_ids: int | str | list[int | str]
                           ) -> None:
        """Reannounce one or more torrents to their trackers."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        for torrent_id in torrent_ids:
            self._call("core.force_reannounce", [[str(torrent_id)]])

    @log_time
    def start_all_torrents(self) -> None:
        """Start all torrents."""
        torrents = self.torrents()
        torrent_ids = [t.id for t in torrents]
        if torrent_ids:
            self._call("core.resume_torrent", [torrent_ids])

    @log_time
    def stop_all_torrents(self) -> None:
        """Stop all torrents."""
        torrents = self.torrents()
        torrent_ids = [t.id for t in torrents]
        if torrent_ids:
            self._call("core.pause_torrent", [torrent_ids])

    @log_time
    def update_labels(self, torrent_ids: int | str | list[int | str],
                      labels: list[str]) -> None:
        """Update labels/tags for one or more torrents.

        Note: Deluge label support depends on the Label plugin being enabled.
        """
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Deluge's label API is plugin-based and limited
        # This is a basic implementation
        for torrent_id in torrent_ids:
            if labels:
                # Set first label (Deluge typically supports single label)
                try:
                    self._call("label.set_torrent",
                               [str(torrent_id), labels[0]])
                except Exception:
                    pass  # Label plugin may not be available

    @log_time
    def get_categories(self) -> list[CategoryDTO]:
        """Get list of available torrent categories.

        Note: Deluge does not support categories.
        """
        return []

    @log_time
    def set_category(self, torrent_ids: int | str | list[int | str],
                     category: str | None) -> None:
        """Set category for one or more torrents.

        Note: Deluge does not support categories. This is a no-op.
        """
        pass

    @log_time
    def edit_torrent(self, torrent_id: int | str, name: str, location: str
                     ) -> None:
        """Edit torrent name and location."""
        torrent = self.torrent(torrent_id)

        if name != torrent.name:
            self._call("core.rename_files", [str(torrent_id), [[0, name]]])

        if location != torrent.download_dir:
            self._call("core.move_storage", [[str(torrent_id)], location])

    @log_time
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits.

        Note: Deluge doesn't have a built-in alt speed mode.
        This is a no-op and always returns False.
        """
        return False

    @log_time
    def set_priority(self, torrent_ids: int | str | list[int | str],
                     priority: int) -> None:
        """Set bandwidth priority for one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        for torrent_id in torrent_ids:
            # Deluge uses different priority mapping
            # -1=low (0), 0=normal (64), 1=high (128)
            deluge_priority = (priority + 1) * 64
            self._call("core.set_torrent_priority",
                       [[str(torrent_id)], deluge_priority])

    @log_time
    def set_file_priority(self, torrent_id: int | str, file_ids: list[int],
                          priority: FilePriority) -> None:
        """Set download priority for files within a torrent."""
        # Map FilePriority enum to Deluge priority values
        # Deluge uses 0=Skip, 1=Low, 4=Normal, 7=High
        priority_map = {
            FilePriority.NOT_DOWNLOADING: 0,
            FilePriority.LOW: 1,
            FilePriority.MEDIUM: 4,
            FilePriority.HIGH: 7,
        }

        deluge_priority = priority_map[priority]

        # Deluge's file priority API
        for file_id in file_ids:
            self._call("core.set_torrent_file_priorities",
                       [str(torrent_id), {file_id: deluge_priority}])
