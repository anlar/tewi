"""qBittorrent torrent client implementation."""

import os
from dataclasses import asdict
from datetime import datetime, timedelta

from qbittorrentapi import Client as QBittorrentAPIClient
from qbittorrentapi.definitions import Dictionary
from qbittorrentapi.torrents import TorrentDictionary, Tracker

from ...util.log import log_time
from ...util.misc import is_torrent_link
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


class QBittorrentClient(BaseClient):
    """qBittorrent client implementation."""

    # Status mapping from qBittorrent to normalized status
    STATUS_MAP = {
        "downloading": "downloading",
        "uploading": "seeding",
        "pausedDL": "stopped",
        "pausedUP": "stopped",
        "stalledDL": "downloading",
        "stalledUP": "seeding",
        "checkingDL": "checking",
        "checkingUP": "checking",
        "checkingResumeData": "checking",
        "queuedDL": "downloading",
        "queuedUP": "seeding",
        "error": "stopped",
        "missingFiles": "stopped",
        "allocating": "downloading",
        "metaDL": "downloading",
        "forcedDL": "downloading",
        "forcedUP": "seeding",
        "moving": "stopped",
    }

    TRACKER_STATUS: dict[int, str] = {
        0: "Disabled",
        1: "Not contacted",
        2: "Working",
        3: "Updating",
        4: "Not working",
    }
    """
    Maps tracker status codes to human-readable status labels.

    0 - Tracker is disabled (used for DHT, PeX, and LSD)
    1 - Tracker has not been contacted yet
    2 - Tracker has been contacted and is working
    3 - Tracker is updating
    4 - Tracker has been contacted, but it is not working (or doesn't
        send proper replies)
    """

    # ========================================================================
    # Client Lifecycle & Metadata
    # ========================================================================

    @log_time
    def __init__(
        self,
        host: str,
        port: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.client = QBittorrentAPIClient(
            host=host,
            port=port,
            username=username or "",
            password=password or "",
        )

        # Authenticate
        try:
            self.client.auth_log_in()
        except Exception as e:
            raise ClientError(f"Failed to authenticate with qBittorrent: {e}")

    def capable(self, capability: ClientCapability) -> bool:
        match capability:
            case ClientCapability.TORRENT_ID:
                return False
            case ClientCapability.SET_PRIORITY:
                return False
            case ClientCapability.CATEGORY:
                return True

        return True

    @log_time
    def meta(self) -> ClientMeta:
        """Get daemon name and version."""
        return {"name": "qBittorrent", "version": self.client.app.version}

    # ========================================================================
    # Session & Global Settings
    # ========================================================================

    @log_time
    def session(self, torrents: list[Torrent]) -> ClientSession:
        transfer_info = self.client.transfer.info
        prefs = self.client.app.preferences

        counts = count_torrents_by_status(torrents)

        # Get free space for download directory
        try:
            main_data = self.client.sync.maindata()
            free_space = main_data.server_state.free_space_on_disk
        except Exception:
            free_space = 0

        # Check if alternative speed limits are enabled
        # Note: speed_limits_mode returns a string '0' or '1', not an integer
        alt_speed_enabled = self.client.transfer.speed_limits_mode == "1"

        return {
            "download_dir": prefs.save_path,
            "download_dir_free_space": free_space,
            "upload_speed": transfer_info.up_info_speed,
            "download_speed": transfer_info.dl_info_speed,
            "alt_speed_enabled": alt_speed_enabled,
            # qBittorrent returns bytes/s - store as-is
            "alt_speed_up": prefs.alt_up_limit,
            "alt_speed_down": prefs.alt_dl_limit,
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
        transfer_info = self.client.transfer.info

        # Current session stats
        current_uploaded = transfer_info.up_info_data
        current_downloaded = transfer_info.dl_info_data
        current_ratio = (
            float("inf")
            if current_downloaded == 0
            else current_uploaded / current_downloaded
        )

        # All-time stats (available in server_state)
        main_data = self.client.sync.maindata()
        server_state = main_data.server_state
        total_uploaded = server_state.alltime_ul
        total_downloaded = server_state.alltime_dl
        total_ratio = (
            float("inf")
            if total_downloaded == 0
            else total_uploaded / total_downloaded
        )

        # Session waste and connected peers (qBittorrent-specific)
        current_waste = getattr(server_state, "total_wasted_session", None)
        current_connected_peers = getattr(
            server_state, "total_peer_connections", None
        )

        # Cache statistics (qBittorrent-specific)
        cache_read_hits_raw = getattr(server_state, "read_cache_hits", None)
        cache_read_hits = (
            float(cache_read_hits_raw)
            if cache_read_hits_raw is not None
            else None
        )
        cache_total_buffers_size = getattr(
            server_state, "total_buffers_size", None
        )

        # Performance statistics (qBittorrent-specific)
        perf_write_cache_overload = getattr(
            server_state, "write_cache_overload", None
        )
        perf_read_cache_overload = getattr(
            server_state, "read_cache_overload", None
        )
        perf_queued_io_jobs = getattr(server_state, "queued_io_jobs", None)
        perf_average_time_queue = getattr(
            server_state, "average_time_queue", None
        )
        perf_total_queued_size = getattr(
            server_state, "total_queued_size", None
        )

        return {
            "current_uploaded_bytes": current_uploaded,
            "current_downloaded_bytes": current_downloaded,
            "current_ratio": current_ratio,
            "current_active_seconds": None,  # qBittorrent doesn't provide this
            "current_waste": current_waste,
            "current_connected_peers": current_connected_peers,
            "total_uploaded_bytes": total_uploaded,
            "total_downloaded_bytes": total_downloaded,
            "total_ratio": total_ratio,
            "total_active_seconds": None,  # qBittorrent doesn't provide this
            "total_started_count": None,  # qBittorrent doesn't provide this
            "cache_read_hits": cache_read_hits,
            "cache_total_buffers_size": cache_total_buffers_size,
            "perf_write_cache_overload": perf_write_cache_overload,
            "perf_read_cache_overload": perf_read_cache_overload,
            "perf_queued_io_jobs": perf_queued_io_jobs,
            "perf_average_time_queue": perf_average_time_queue,
            "perf_total_queued_size": perf_total_queued_size,
        }

    @log_time
    def preferences(self) -> dict[str, str]:
        """Get session preferences as key-value pairs."""
        prefs = self.client.app.preferences
        # Convert preferences object to dict and filter
        prefs_dict = prefs.dict() if hasattr(prefs, "dict") else dict(prefs)
        return {k: str(v) for k, v in sorted(prefs_dict.items())}

    @log_time
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits."""
        current_state = self.client.transfer.speed_limits_mode
        # Toggle: '0' = normal, '1' = alternative (API returns strings)
        new_state = "0" if current_state == "1" else "1"
        self.client.transfer.set_speed_limits_mode(mode=new_state)
        return new_state == "1"

    # ========================================================================
    # Torrent Retrieval
    # ========================================================================

    @log_time
    def torrents(self) -> list[Torrent]:
        """Get list of all torrents."""
        qb_torrents = self.client.torrents.info()
        return [self._torrent_to_dto(t) for t in qb_torrents]

    @log_time
    def torrent(self, hash: str) -> TorrentDetail:
        """Get detailed information about a specific torrent."""
        # Get the torrent directly by hash
        qb_torrents = self.client.torrents.info(torrent_hashes=hash)

        if not qb_torrents:
            raise ClientError(f"Torrent with hash {hash} not found")

        return self._torrent_detail_to_dto(qb_torrents[0])

    # ========================================================================
    # Torrent Lifecycle Operations
    # ========================================================================

    @log_time
    def add_torrent(self, value: str) -> None:
        """Add a torrent from magnet link or file path."""
        if is_torrent_link(value):
            self.client.torrents.add(urls=value)
        else:
            file = os.path.expanduser(value)
            with open(file, "rb") as f:
                self.client.torrents.add(torrent_files=f)

    @log_time
    def start_torrent(self, hashes: str | list[str]) -> None:
        """Start one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.torrents.resume(torrent_hashes=hashes)

    @log_time
    def start_all_torrents(self) -> None:
        """Start all torrents."""
        self.client.torrents.resume(torrent_hashes="all")

    @log_time
    def stop_torrent(self, hashes: str | list[str]) -> None:
        """Stop one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.torrents.pause(torrent_hashes=hashes)

    @log_time
    def stop_all_torrents(self) -> None:
        """Stop all torrents."""
        self.client.torrents.pause(torrent_hashes="all")

    @log_time
    def remove_torrent(
        self,
        hashes: str | list[str],
        delete_data: bool = False,
    ) -> None:
        """Remove one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.torrents.delete(
            delete_files=delete_data, torrent_hashes=hashes
        )

    @log_time
    def verify_torrent(self, hashes: str | list[str]) -> None:
        """Verify one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.torrents.recheck(torrent_hashes=hashes)

    @log_time
    def reannounce_torrent(self, hashes: str | list[str]) -> None:
        """Reannounce one or more torrents to their trackers."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.torrents.reannounce(torrent_hashes=hashes)

    # ========================================================================
    # Torrent Organization & Metadata
    # ========================================================================

    @log_time
    def edit_torrent(self, hash: str, name: str, location: str) -> None:
        torrent = self.torrent(hash)

        if name != torrent.name:
            self.client.torrents.rename(
                torrent_hash=hash, new_torrent_name=name
            )

        if location != torrent.download_dir:
            self.client.torrents.set_location(
                torrent_hashes=hash, location=location
            )

    @log_time
    def get_categories(self) -> list[TorrentCategory]:
        """Get list of available torrent categories."""
        try:
            categories_dict = self.client.torrents_categories()
            categories = []
            for name, data in categories_dict.items():
                save_path = data.get("savePath") or None
                categories.append(
                    TorrentCategory(name=name, save_path=save_path)
                )
            return sorted(categories, key=lambda c: c.name)
        except Exception:
            return []

    @log_time
    def set_category(
        self, hashes: str | list[str], category: str | None
    ) -> None:
        """Set category for one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        # qBittorrent API accepts empty string for clearing category
        category_value = category if category else ""

        for hash_str in hashes:
            self.client.torrents_set_category(
                category=category_value, torrent_hashes=hash_str
            )

    @log_time
    def update_labels(self, hashes: str | list[str], labels: list[str]) -> None:
        """Update labels/tags for one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        # Convert labels list to comma-separated string for qBittorrent
        tags_str = ",".join(labels) if labels else ""

        for hash_str in hashes:
            # Get current torrent to find existing tags
            torrents = self.client.torrents.info(torrent_hashes=hash_str)
            if torrents:
                existing_tags = torrents[0].tags
                # If there are existing tags, remove them first
                if existing_tags:
                    try:
                        self.client.torrents_delete_tags(
                            tags=existing_tags, torrent_hashes=hash_str
                        )
                    except Exception:
                        pass  # Ignore if tag removal fails

            # Add new tags
            if tags_str:
                try:
                    self.client.torrents_add_tags(
                        tags=tags_str, torrent_hashes=hash_str
                    )
                except Exception:
                    pass  # Ignore if tag addition fails

    # ========================================================================
    # Priority Management
    # ========================================================================

    @log_time
    def set_priority(self, hashes: str | list[str], priority: int) -> None:
        """Set bandwidth priority for one or more torrents.

        Note: qBittorrent doesn't support whole-torrent bandwidth priority
        (only individual file priorities and queue positions). This method
        is a no-op for qBittorrent.
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
        # Map TorrentFilePriority enum to qBittorrent priority values
        priority_map = {
            TorrentFilePriority.NOT_DOWNLOADING: 0,
            TorrentFilePriority.LOW: 1,
            TorrentFilePriority.MEDIUM: 6,
            TorrentFilePriority.HIGH: 7,
        }

        qb_priority = priority_map[priority]

        # Set priority for each file
        self.client.torrents.file_priority(
            torrent_hash=hash, file_ids=file_ids, priority=qb_priority
        )

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    @log_time
    def _normalize_status(self, qb_status: str) -> str:
        """Normalize qBittorrent status to common status string."""
        return self.STATUS_MAP.get(qb_status, "stopped")

    @log_time
    def _torrent_to_dto(self, torrent: TorrentDictionary) -> Torrent:
        """Convert qBittorrent torrent to Torrent.

        Populates list view fields only.
        """
        # Calculate ETA
        if torrent.dlspeed > 0 and torrent.amount_left > 0:
            eta_seconds = torrent.amount_left / torrent.dlspeed
            eta = timedelta(seconds=int(eta_seconds))
        else:
            eta = timedelta(seconds=-1)  # Transmission uses -1 for unknown

        return Torrent(
            id=None,  # qBittorrent doesn't use numeric IDs
            hash=torrent.hash,
            name=torrent.name,
            status=self._normalize_status(torrent.state),
            total_size=torrent.total_size,
            size_when_done=torrent.size,
            left_until_done=torrent.amount_left,
            percent_done=torrent.progress,
            eta=eta,
            rate_upload=torrent.upspeed,
            rate_download=torrent.dlspeed,
            ratio=torrent.ratio,
            peers_connected=torrent.num_leechs + torrent.num_seeds,
            peers_getting_from_us=torrent.num_leechs,
            peers_sending_to_us=torrent.num_seeds,
            uploaded_ever=torrent.uploaded,
            # qBittorrent doesn't have whole-torrent priority
            priority=None,
            added_date=(
                datetime.fromtimestamp(torrent.added_on)
                if torrent.added_on > 0
                else datetime.now()
            ),
            activity_date=(
                datetime.fromtimestamp(torrent.last_activity)
                if torrent.last_activity > 0
                else datetime.now()
            ),
            queue_position=torrent.priority if torrent.priority > 0 else None,
            download_dir=torrent.save_path,
            category=torrent.category if torrent.category else None,
            labels=[tag.strip() for tag in torrent.tags.split(",")]
            if torrent.tags
            else [],
        )

    @log_time
    def _torrent_detail_to_dto(
        self, torrent: TorrentDictionary
    ) -> TorrentDetail:
        """Convert qBittorrent torrent to TorrentDetail.

        Reuses _torrent_to_dto for base fields and adds detail-specific
        fields plus files, peers, and trackers.
        """

        # Get base torrent data
        base_torrent = self._torrent_to_dto(torrent)
        base_dict = asdict(base_torrent)

        # Get piece information from properties
        try:
            props = self.client.torrents.properties(torrent_hash=torrent.hash)
            piece_size = props.piece_size
            piece_count = props.pieces_num
        except Exception:
            piece_size = 0
            piece_count = 0

        # Parse files, peers, and trackers
        files_data = self.client.torrents.files(torrent_hash=torrent.hash)
        files = [self._file_to_dto(f, torrent.hash) for f in files_data]

        # Get peers
        try:
            peers_data = self.client.sync.torrent_peers(
                torrent_hash=torrent.hash
            )
            peers = [self._peer_to_dto(p) for p in peers_data.peers.values()]
        except Exception:
            peers = []

        # Get trackers
        trackers_data = self.client.torrents.trackers(torrent_hash=torrent.hash)
        trackers = [self._tracker_to_dto(t) for t in trackers_data]

        return TorrentDetail(
            **base_dict,
            hash_string=torrent.hash,
            piece_count=piece_count,
            piece_size=piece_size,
            is_private=getattr(torrent, "is_private", False),
            comment=torrent.comment if torrent.comment else "",
            creator=torrent.created_by
            if hasattr(torrent, "created_by")
            else "",
            downloaded_ever=torrent.downloaded,
            error_string="",  # qBittorrent doesn't provide error string
            start_date=(
                datetime.fromtimestamp(torrent.completion_on)
                if hasattr(torrent, "completion_on")
                and torrent.completion_on > 0
                else None
            ),
            done_date=(
                datetime.fromtimestamp(torrent.completion_on)
                if torrent.completion_on > 0
                else None
            ),
            files=files,
            peers=peers,
            trackers=trackers,
        )

    @log_time
    def _file_to_dto(self, file: Dictionary, torrent_hash: str) -> TorrentFile:
        """Convert qBittorrent file to TorrentFile."""

        match file.priority:
            case 0:
                priority = TorrentFilePriority.NOT_DOWNLOADING
            case 1:
                priority = TorrentFilePriority.LOW
            case 6:
                priority = TorrentFilePriority.MEDIUM
            case 7:
                priority = TorrentFilePriority.HIGH

        return TorrentFile(
            id=file.index,
            name=file.name,
            size=file.size,
            completed=int(file.size * file.progress),
            priority=priority,
        )

    @log_time
    def _peer_to_dto(self, peer: Dictionary) -> TorrentPeer:
        """Convert qBittorrent peer to TorrentPeer."""

        match peer.connection:
            case "BT":
                connection_type = "TCP"
            case None:
                connection_type = "Unknown"
            case _:
                connection_type = peer.connection

        # Determine direction from 'I' flag in flags string
        direction = "Incoming" if "I" in peer.flags else "Outgoing"

        if "D" in peer.flags:
            dl_state = TorrentPeerState.INTERESTED
        elif "d" in peer.flags:
            dl_state = TorrentPeerState.CHOKED
        else:
            dl_state = TorrentPeerState.NONE

        if "U" in peer.flags:
            ul_state = TorrentPeerState.INTERESTED
        elif "u" in peer.flags:
            ul_state = TorrentPeerState.CHOKED
        else:
            ul_state = TorrentPeerState.NONE

        return TorrentPeer(
            address=peer.ip,
            client_name=peer.client,
            progress=peer.progress,
            is_encrypted=peer.connection.startswith("uTP") or "E" in peer.flags,
            rate_to_client=peer.dl_speed,
            rate_to_peer=peer.up_speed,
            flag_str=peer.flags,
            port=peer.port if hasattr(peer, "port") else -1,
            connection_type=connection_type,
            direction=direction,
            country=peer.country.split(",", 1)[0] if peer.country else None,
            dl_state=dl_state,
            ul_state=ul_state,
        )

    @log_time
    def _tracker_to_dto(self, t: Tracker) -> TorrentTracker:
        """Convert qBittorrent tracker to TorrentTracker."""

        return TorrentTracker(
            host=t.url,
            tier=t.tier if t.tier >= 0 else None,
            status=self.TRACKER_STATUS.get(
                t.status, self.TRACKER_STATUS_UNKNOWN
            ),
            message=t.msg,
            peer_count=t.num_peers if t.num_peers >= 0 else None,
            seeder_count=t.num_seeds if t.num_seeds >= 0 else None,
            leecher_count=t.num_leeches if t.num_leeches >= 0 else None,
            download_count=t.num_downloaded if t.num_downloaded >= 0 else None,
        )
