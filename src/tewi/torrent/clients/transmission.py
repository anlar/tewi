"""Transmission torrent client implementation."""

import os
import pathlib
from dataclasses import asdict
from datetime import datetime

from transmission_rpc import Client as TransmissionRPCClient
from transmission_rpc import File as TransmissionFile
from transmission_rpc import Torrent as TransmissionTorrent
from transmission_rpc.torrent import Tracker as TransmissionTracker

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


class TransmissionClient(BaseClient):
    """Transmission torrent client implementation."""

    # Transmission bandwidth priority values
    PRIORITY_LOW = -1
    PRIORITY_NORMAL = 0
    PRIORITY_HIGH = 1

    # Tracker announce state codes to human-readable status labels
    TRACKER_ANNOUNCE_STATE: dict[int, str] = {
        0: "Inactive",
        1: "Waiting",
        2: "Queued",
        3: "Active",
    }

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
        kwargs = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
        }
        if path is not None:
            kwargs["path"] = path

        self.client = TransmissionRPCClient(**kwargs)

    @log_time
    def capable(self, capability: ClientCapability) -> bool:
        if capability == ClientCapability.CATEGORY:
            return False

        return True

    @log_time
    def meta(self) -> ClientMeta:
        return {
            "name": "Transmission",
            "version": self.client.get_session().version,
        }

    # ========================================================================
    # Session & Global Settings
    # ========================================================================

    @log_time
    def session(self, torrents: list[Torrent]) -> ClientSession:
        s = self.client.get_session()
        stats = self.client.session_stats()

        counts = count_torrents_by_status(torrents)

        return {
            "download_dir": s.download_dir,
            "download_dir_free_space": s.download_dir_free_space,
            "upload_speed": stats.upload_speed,
            "download_speed": stats.download_speed,
            "alt_speed_enabled": s.alt_speed_enabled,
            # Transmission returns KB/s - convert to bytes/s for consistency
            "alt_speed_up": s.alt_speed_up * 1000,
            "alt_speed_down": s.alt_speed_down * 1000,
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
        s = self.client.session_stats()

        return {
            "current_uploaded_bytes": s.current_stats.uploaded_bytes,
            "current_downloaded_bytes": s.current_stats.downloaded_bytes,
            "current_ratio": self._calculate_ratio(
                s.current_stats.downloaded_bytes, s.current_stats.uploaded_bytes
            ),
            "current_active_seconds": s.current_stats.seconds_active,
            "current_waste": None,
            "current_connected_peers": None,
            "total_uploaded_bytes": s.cumulative_stats.uploaded_bytes,
            "total_downloaded_bytes": s.cumulative_stats.downloaded_bytes,
            "total_ratio": self._calculate_ratio(
                s.cumulative_stats.downloaded_bytes,
                s.cumulative_stats.uploaded_bytes,
            ),
            "total_active_seconds": s.cumulative_stats.seconds_active,
            "total_started_count": s.cumulative_stats.session_count,
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
        session_dict = self.client.get_session().fields

        excluded_prefixes = ("units", "version")
        filtered = {
            k: v
            for k, v in session_dict.items()
            if not k.startswith(excluded_prefixes)
        }

        return dict(sorted(filtered.items()))

    @log_time
    def toggle_alt_speed(self) -> bool:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled=not alt_speed_enabled)
        return not alt_speed_enabled

    # ========================================================================
    # Torrent Retrieval
    # ========================================================================

    @log_time
    def torrents(self) -> list[Torrent]:
        torrents = self.client.get_torrents(
            arguments=[
                "id",
                "hashString",
                "name",
                "status",
                "totalSize",
                "downloadDir",
                "left_until_done",
                "percentDone",
                "eta",
                "rateUpload",
                "rateDownload",
                "uploadRatio",
                "sizeWhenDone",
                "leftUntilDone",
                "addedDate",
                "activityDate",
                "queuePosition",
                "peersConnected",
                "peersGettingFromUs",
                "peersSendingToUs",
                "bandwidthPriority",
                "uploadedEver",
                "labels",
            ]
        )

        return [self._torrent_to_dto(t) for t in torrents]

    @log_time
    def torrent(self, hash: str) -> TorrentDetail:
        """Get detailed information about a specific torrent."""
        torrent = self.client.get_torrent(hash)
        return self._torrent_detail_to_dto(torrent)

    # ========================================================================
    # Torrent Lifecycle Operations
    # ========================================================================

    @log_time
    def add_torrent(self, value: str) -> None:
        if is_torrent_link(value):
            self.client.add_torrent(value)
        else:
            file = os.path.expanduser(value)
            if not os.path.exists(file):
                raise ClientError(f"Torrent file not found: {file}")
            self.client.add_torrent(pathlib.Path(file))

    @log_time
    def start_torrent(self, hashes: str | list[str]) -> None:
        self.client.start_torrent(hashes)

    @log_time
    def start_all_torrents(self) -> None:
        self.client.start_all()

    @log_time
    def stop_torrent(self, hashes: str | list[str]) -> None:
        self.client.stop_torrent(hashes)

    @log_time
    def stop_all_torrents(self) -> None:
        torrents = self.client.get_torrents(arguments=["hashString"])
        self.stop_torrent([t.hash_string for t in torrents])

    @log_time
    def remove_torrent(
        self,
        hashes: str | list[str],
        delete_data: bool = False,
    ) -> None:
        self.client.remove_torrent(hashes, delete_data=delete_data)

    @log_time
    def verify_torrent(self, hashes: str | list[str]) -> None:
        self.client.verify_torrent(hashes)

    @log_time
    def reannounce_torrent(self, hashes: str | list[str]) -> None:
        self.client.reannounce_torrent(hashes)

    # ========================================================================
    # Torrent Organization & Metadata
    # ========================================================================

    @log_time
    def edit_torrent(self, hash: str, name: str, location: str) -> None:
        torrent = self.torrent(hash)

        if name != torrent.name:
            self.client.rename_torrent_path(hash, torrent.name, name)

        if location != torrent.download_dir:
            self.client.move_torrent_data(hash, location)

    @log_time
    def get_categories(self) -> list[TorrentCategory]:
        """Get list of available torrent categories.

        Note: Transmission does not support categories.
        """
        raise ClientError("Transmission doesn't support categories")

    @log_time
    def set_category(
        self, hashes: str | list[str], category: str | None
    ) -> None:
        """Set category for one or more torrents.

        Note: Transmission does not support categories.
        """
        raise ClientError("Transmission doesn't support categories")

    @log_time
    def update_labels(self, hashes: str | list[str], labels: list[str]) -> None:
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.change_torrent(hashes, labels=labels)

    # ========================================================================
    # Priority Management
    # ========================================================================

    @log_time
    def set_priority(self, hashes: str | list[str], priority: int) -> None:
        """Set bandwidth priority for one or more torrents."""
        if isinstance(hashes, str):
            hashes = [hashes]

        self.client.change_torrent(hashes, bandwidth_priority=priority)

    @log_time
    def set_file_priority(
        self,
        hash: str,
        file_ids: list[int],
        priority: TorrentFilePriority,
    ) -> None:
        """Set download priority for files within a torrent."""
        # Transmission uses different arguments based on priority:
        # - files_wanted/files_unwanted for selection
        # - priority_high/priority_low/priority_normal for priority
        args = {}

        match priority:
            case TorrentFilePriority.NOT_DOWNLOADING:
                args["files_unwanted"] = file_ids
            case TorrentFilePriority.LOW:
                args["files_wanted"] = file_ids
                args["priority_low"] = file_ids
            case TorrentFilePriority.MEDIUM:
                args["files_wanted"] = file_ids
                args["priority_normal"] = file_ids
            case TorrentFilePriority.HIGH:
                args["files_wanted"] = file_ids
                args["priority_high"] = file_ids

        self.client.change_torrent(hash, **args)

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    @log_time
    def _torrent_to_dto(self, torrent: TransmissionTorrent) -> Torrent:
        """Convert transmission-rpc Torrent to Torrent DTO.

        Populates list view fields only.
        """
        return Torrent(
            id=torrent.id,
            hash=torrent.hash_string,
            name=torrent.name,
            status=torrent.status,
            total_size=torrent.total_size,
            size_when_done=torrent.size_when_done,
            left_until_done=torrent.left_until_done,
            percent_done=torrent.percent_done,
            eta=torrent.eta,
            rate_upload=torrent.rate_upload,
            rate_download=torrent.rate_download,
            ratio=torrent.ratio,
            peers_connected=torrent.peers_connected,
            peers_getting_from_us=torrent.peers_getting_from_us,
            peers_sending_to_us=torrent.peers_sending_to_us,
            uploaded_ever=torrent.uploaded_ever,
            priority=torrent.priority,
            added_date=torrent.added_date,
            activity_date=torrent.activity_date,
            queue_position=torrent.queue_position,
            download_dir=torrent.download_dir,
            category=None,  # Transmission does not support categories
            labels=list(torrent.labels) if torrent.labels else [],
        )

    @log_time
    def _torrent_detail_to_dto(
        self, torrent: TransmissionTorrent
    ) -> TorrentDetail:
        """Convert transmission-rpc Torrent to TorrentDetail.

        Reuses _torrent_to_dto for base fields and adds detail-specific
        fields plus files, peers, and trackers.
        """

        # Get base torrent data
        base_torrent = self._torrent_to_dto(torrent)
        base_dict = asdict(base_torrent)

        # Parse files, peers, and trackers
        files = [self._file_to_dto(f) for f in torrent.get_files()]
        peers = [self._peer_to_dto(p) for p in torrent.peers]
        trackers = [self._tracker_to_dto(t) for t in torrent.tracker_stats]

        return TorrentDetail(
            **base_dict,
            hash_string=torrent.hash_string,
            piece_count=torrent.piece_count,
            piece_size=torrent.piece_size,
            is_private=torrent.is_private,
            comment=torrent.comment,
            creator=torrent.creator,
            downloaded_ever=torrent.downloaded_ever,
            error_string=torrent.error_string,
            start_date=torrent.start_date,
            done_date=torrent.done_date,
            files=files,
            peers=peers,
            trackers=trackers,
        )

    @log_time
    def _file_to_dto(self, file: TransmissionFile) -> TorrentFile:
        """Convert transmission-rpc File to TorrentFile."""

        if file.selected:
            match file.priority:
                case self.PRIORITY_LOW:
                    priority = TorrentFilePriority.LOW
                case self.PRIORITY_NORMAL:
                    priority = TorrentFilePriority.MEDIUM
                case self.PRIORITY_HIGH:
                    priority = TorrentFilePriority.HIGH
        else:
            priority = TorrentFilePriority.NOT_DOWNLOADING

        return TorrentFile(
            id=file.id,
            name=file.name,
            size=file.size,
            completed=file.completed,
            priority=priority,
        )

    @log_time
    def _peer_to_dto(self, peer: dict[str, object]) -> TorrentPeer:
        """Convert transmission-rpc peer dict to TorrentPeer."""

        connection_type = "μTP" if peer.get("isUTP", False) else "TCP"

        direction = "Incoming" if peer.get("isIncoming", False) else "Outgoing"

        dl_state = self._get_peer_state(
            peer["clientIsInterested"], peer["clientIsChoked"]
        )
        ul_state = self._get_peer_state(
            peer["peerIsInterested"], peer["peerIsChoked"]
        )

        return TorrentPeer(
            address=peer["address"],
            client_name=peer["clientName"],
            progress=peer["progress"],
            is_encrypted=peer["isEncrypted"],
            rate_to_client=peer["rateToClient"],
            rate_to_peer=peer["rateToPeer"],
            flag_str=peer["flagStr"],
            port=peer.get("port", -1),
            connection_type=connection_type,
            direction=direction,
            country=None,
            dl_state=dl_state,
            ul_state=ul_state,
        )

    @log_time
    def _tracker_to_dto(self, t: TransmissionTracker) -> TorrentTracker:
        """Convert transmission-rpc Tracker to TorrentTracker."""

        return TorrentTracker(
            host=t.host,
            tier=t.tier,
            seeder_count=t.seeder_count if t.seeder_count >= 0 else None,
            leecher_count=t.leecher_count if t.leecher_count >= 0 else None,
            download_count=t.download_count if t.download_count >= 0 else None,
            peer_count=t.last_announce_peer_count
            if t.last_announce_peer_count >= 0
            else None,
            status=self.TRACKER_ANNOUNCE_STATE.get(
                t.announce_state, self.TRACKER_STATUS_UNKNOWN
            ),
            message=t.last_announce_result,
            last_announce=self._ts_to_dt(t.last_announce_time),
            next_announce=self._ts_to_dt(t.next_announce_time),
            last_scrape=self._ts_to_dt(t.last_scrape_time),
            next_scrape=self._ts_to_dt(t.next_scrape_time),
        )

    @staticmethod
    @log_time
    def _calculate_ratio(downloaded: int, uploaded: int) -> float:
        """Calculate download ratio (zero div safe)."""
        if downloaded == 0:
            return float("inf")
        else:
            return uploaded / downloaded

    @staticmethod
    @log_time
    def _ts_to_dt(timestamp: int) -> datetime | None:
        """Convert Unix timestamp to datetime (None for invalid values)."""
        return datetime.fromtimestamp(timestamp) if timestamp > 0 else None

    @staticmethod
    @log_time
    def _get_peer_state(
        is_interested: bool, is_choked: bool
    ) -> TorrentPeerState:
        """Determine peer state from interest and choke flags."""
        if not is_interested:
            return TorrentPeerState.NONE
        if is_choked:
            return TorrentPeerState.CHOKED
        return TorrentPeerState.INTERESTED
