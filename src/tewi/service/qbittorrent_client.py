"""qBittorrent torrent client implementation."""

import os
from datetime import datetime, timedelta

from qbittorrentapi import Client as QBittorrentAPIClient

from ..util.misc import is_torrent_link
from ..util.decorator import log_time
from ..common import SortOrder, TorrentDTO, TorrentDetailDTO, FileDTO, PeerDTO, TrackerDTO
from .base_client import BaseClient, ClientMeta, ClientStats, ClientSession, ClientError


class QBittorrentClient(BaseClient):
    """qBittorrent client implementation."""

    # Status mapping from qBittorrent to normalized status
    STATUS_MAP = {
        'downloading': 'downloading',
        'uploading': 'seeding',
        'pausedDL': 'stopped',
        'pausedUP': 'stopped',
        'stalledDL': 'downloading',
        'stalledUP': 'seeding',
        'checkingDL': 'checking',
        'checkingUP': 'checking',
        'checkingResumeData': 'checking',
        'queuedDL': 'downloading',
        'queuedUP': 'seeding',
        'error': 'stopped',
        'missingFiles': 'stopped',
        'allocating': 'downloading',
        'metaDL': 'downloading',
        'forcedDL': 'downloading',
        'forcedUP': 'seeding',
        'moving': 'stopped',
    }

    # Priority mapping from qBittorrent (0, 1, 6, 7) to Transmission (-1, 0, 1)
    PRIORITY_TO_TRANSMISSION = {
        0: -1,   # Do not download -> Low
        1: 0,    # Normal -> Normal
        6: 1,    # High -> High
        7: 1,    # Maximum -> High
    }

    # Priority mapping from Transmission to qBittorrent
    PRIORITY_FROM_TRANSMISSION = {
        -1: 0,   # Low -> Do not download
        0: 1,    # Normal -> Normal
        1: 6,    # High -> High
    }

    @log_time
    def __init__(self,
                 host: str, port: str,
                 username: str = None, password: str = None):

        self.client = QBittorrentAPIClient(
            host=host,
            port=port,
            username=username or '',
            password=password or ''
        )

        # Authenticate
        try:
            self.client.auth_log_in()
        except Exception as e:
            raise ClientError(f"Failed to authenticate with qBittorrent: {e}")

    @log_time
    def meta(self) -> ClientMeta:
        """Get daemon name and version."""
        return {
            'name': 'qBittorrent',
            'version': self.client.app.version
        }

    @log_time
    def stats(self) -> ClientStats:
        """Get current and cumulative session statistics."""
        transfer_info = self.client.transfer.info

        # Current session stats
        current_uploaded = transfer_info.up_info_data
        current_downloaded = transfer_info.dl_info_data
        current_ratio = (
            float('inf')
            if current_downloaded == 0
            else current_uploaded / current_downloaded
        )

        # All-time stats (available in server_state)
        main_data = self.client.sync.maindata()
        server_state = main_data.server_state
        total_uploaded = server_state.alltime_ul
        total_downloaded = server_state.alltime_dl
        total_ratio = (
            float('inf')
            if total_downloaded == 0
            else total_uploaded / total_downloaded
        )

        return {
            'current_uploaded_bytes': current_uploaded,
            'current_downloaded_bytes': current_downloaded,
            'current_ratio': current_ratio,
            'current_active_seconds': None,  # qBittorrent doesn't provide this
            'total_uploaded_bytes': total_uploaded,
            'total_downloaded_bytes': total_downloaded,
            'total_ratio': total_ratio,
            'total_active_seconds': None,  # qBittorrent doesn't provide this
            'total_started_count': None,  # qBittorrent doesn't provide this
        }

    @log_time
    def session(self, torrents: list[TorrentDTO], sort_order: SortOrder, sort_order_asc: bool) -> ClientSession:
        transfer_info = self.client.transfer.info
        prefs = self.client.app.preferences

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

        torrents_stop = torrents_count - torrents_down - torrents_seed - torrents_check

        # Get free space for download directory
        try:
            main_data = self.client.sync.maindata()
            free_space = main_data.server_state.free_space_on_disk
        except Exception:
            free_space = 0

        # Check if alternative speed limits are enabled
        # Note: speed_limits_mode returns a string '0' or '1', not an integer
        alt_speed_enabled = self.client.transfer.speed_limits_mode == '1'

        return {
            'download_dir': prefs.save_path,
            'download_dir_free_space': free_space,
            'upload_speed': transfer_info.up_info_speed,
            'download_speed': transfer_info.dl_info_speed,
            'alt_speed_enabled': alt_speed_enabled,
            # qBittorrent returns bytes/s - store as-is
            'alt_speed_up': prefs.alt_up_limit,
            'alt_speed_down': prefs.alt_dl_limit,
            'torrents_complete_size': torrents_complete_size,
            'torrents_total_size': torrents_total_size,
            'torrents_count': torrents_count,
            'torrents_down': torrents_down,
            'torrents_seed': torrents_seed,
            'torrents_check': torrents_check,
            'torrents_stop': torrents_stop,
            'sort_order': sort_order,
            'sort_order_asc': sort_order_asc,
        }

    @log_time
    def preferences(self) -> dict[str, str]:
        """Get session preferences as key-value pairs."""
        prefs = self.client.app.preferences
        # Convert preferences object to dict and filter
        prefs_dict = prefs.dict() if hasattr(prefs, 'dict') else dict(prefs)
        return {k: str(v) for k, v in sorted(prefs_dict.items())}

    @log_time
    def _normalize_status(self, qb_status: str) -> str:
        """Normalize qBittorrent status to common status string."""
        return self.STATUS_MAP.get(qb_status, 'stopped')

    @log_time
    def _torrent_to_dto(self, torrent) -> TorrentDTO:
        """Convert qBittorrent torrent to TorrentDTO."""
        # Calculate ETA
        if torrent.dlspeed > 0 and torrent.amount_left > 0:
            eta_seconds = torrent.amount_left / torrent.dlspeed
            eta = timedelta(seconds=int(eta_seconds))
        else:
            eta = timedelta(seconds=-1)  # Transmission uses -1 for unknown

        return TorrentDTO(
            id=torrent.hash,  # qBittorrent uses hash as ID
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
            priority=None,  # qBittorrent doesn't have whole-torrent priority (like Transmission)
            added_date=(datetime.fromtimestamp(torrent.added_on)
                        if torrent.added_on > 0 else datetime.now()),
            activity_date=(datetime.fromtimestamp(torrent.last_activity)
                           if torrent.last_activity > 0 else datetime.now()),
            queue_position=torrent.priority if torrent.priority > 0 else None,
            labels=[tag.strip() for tag in torrent.tags.split(',')] if torrent.tags else [],
        )

    @log_time
    def torrents(self) -> list[TorrentDTO]:
        """Get list of all torrents."""
        qb_torrents = self.client.torrents.info()
        return [self._torrent_to_dto(t) for t in qb_torrents]

    @log_time
    def torrent(self, id: int | str) -> TorrentDetailDTO:
        """Get detailed information about a specific torrent."""
        # In qBittorrent, the ID is the hash string itself
        # Get the torrent directly by hash
        qb_torrents = self.client.torrents.info(torrent_hashes=id)

        if not qb_torrents:
            raise ClientError(f"Torrent with ID {id} not found")

        return self._torrent_detail_to_dto(qb_torrents[0])

    @log_time
    def _file_to_dto(self, file, torrent_hash: str) -> FileDTO:
        """Convert qBittorrent file to FileDTO."""
        # Map qBittorrent priority (0, 1, 6, 7) to Transmission (-1, 0, 1)
        priority = self.PRIORITY_TO_TRANSMISSION.get(file.priority, 0)

        return FileDTO(
            id=file.index,
            name=file.name,
            size=file.size,
            completed=int(file.size * file.progress),
            selected=file.priority > 0,  # In qBittorrent, priority 0 means "do not download"
            priority=priority,
        )

    @log_time
    def _peer_to_dto(self, peer) -> PeerDTO:
        """Convert qBittorrent peer to PeerDTO."""
        # Get connection type (qBittorrent provides detailed connection string)
        connection_type = peer.connection if hasattr(peer, 'connection') else "Unknown"

        # Determine direction from 'I' flag in flags string
        direction = "Incoming" if 'I' in peer.flags else "Outgoing"

        return PeerDTO(
            address=peer.ip,
            client_name=peer.client,
            progress=peer.progress,
            is_encrypted=peer.connection.startswith('uTP') or 'E' in peer.flags,
            rate_to_client=peer.dl_speed,
            rate_to_peer=peer.up_speed,
            flag_str=peer.flags,
            port=peer.port if hasattr(peer, 'port') else -1,
            connection_type=connection_type,
            direction=direction,
        )

    @log_time
    def _tracker_to_dto(self, tracker) -> TrackerDTO:
        """Convert qBittorrent tracker to TrackerDTO."""
        # Map qBittorrent status to readable text
        # 0 = disabled, 1 = not contacted, 2 = working, 3 = updating, 4 = not working
        status_map = {
            0: "Disabled",
            1: "Not contacted",
            2: "Working",
            3: "Updating",
            4: "Not working"
        }
        status = status_map.get(tracker.status, "Unknown")

        # Get message (error or status message from tracker)
        message = tracker.msg if hasattr(tracker, 'msg') and tracker.msg else ""

        # Get peer count reported by tracker
        peer_count = tracker.num_peers if hasattr(tracker, 'num_peers') else -1

        return TrackerDTO(
            host=tracker.url,
            tier=tracker.tier,
            seeder_count=tracker.num_seeds,
            leecher_count=tracker.num_leeches,
            download_count=tracker.num_downloaded,
            status=status,
            message=message,
            peer_count=peer_count,
        )

    @log_time
    def _torrent_detail_to_dto(self, torrent) -> TorrentDetailDTO:
        """Convert qBittorrent torrent to TorrentDetailDTO."""
        # Get files
        files_data = self.client.torrents.files(torrent_hash=torrent.hash)
        files = [self._file_to_dto(f, torrent.hash) for f in files_data]

        # Get peers
        try:
            peers_data = self.client.sync.torrent_peers(torrent_hash=torrent.hash)
            peers = [self._peer_to_dto(p) for p in peers_data.peers.values()]
        except Exception:
            peers = []

        # Get trackers
        trackers_data = self.client.torrents.trackers(torrent_hash=torrent.hash)
        trackers = [self._tracker_to_dto(t) for t in trackers_data]

        # Get piece information from properties
        try:
            props = self.client.torrents.properties(torrent_hash=torrent.hash)
            piece_size = props.piece_size
            piece_count = props.pieces_num
        except Exception:
            piece_size = 0
            piece_count = 0

        return TorrentDetailDTO(
            id=torrent.hash,
            name=torrent.name,
            hash_string=torrent.hash,
            total_size=torrent.total_size,
            piece_count=piece_count,
            piece_size=piece_size,
            is_private=getattr(torrent, 'is_private', False),
            comment=torrent.comment if torrent.comment else "",
            creator=torrent.created_by if hasattr(torrent, 'created_by') else "",
            labels=[tag.strip() for tag in torrent.tags.split(',')] if torrent.tags else [],
            status=self._normalize_status(torrent.state),
            download_dir=torrent.save_path,
            downloaded_ever=torrent.downloaded,
            uploaded_ever=torrent.uploaded,
            ratio=torrent.ratio,
            error_string="",  # qBittorrent doesn't provide error string in the same way
            added_date=(datetime.fromtimestamp(torrent.added_on)
                        if torrent.added_on > 0 else datetime.now()),
            start_date=(datetime.fromtimestamp(torrent.completion_on)
                        if hasattr(torrent, 'completion_on') and torrent.completion_on > 0
                        else None),
            done_date=(datetime.fromtimestamp(torrent.completion_on)
                       if torrent.completion_on > 0 else None),
            activity_date=(datetime.fromtimestamp(torrent.last_activity)
                           if torrent.last_activity > 0 else datetime.now()),
            peers_connected=torrent.num_leechs + torrent.num_seeds,
            peers_sending_to_us=torrent.num_seeds,
            peers_getting_from_us=torrent.num_leechs,
            files=files,
            peers=peers,
            trackers=trackers,
        )

    @log_time
    def add_torrent(self, value: str) -> None:
        """Add a torrent from magnet link or file path."""
        if is_torrent_link(value):
            self.client.torrents.add(urls=value)
        else:
            file = os.path.expanduser(value)
            with open(file, 'rb') as f:
                self.client.torrents.add(torrent_files=f)

    @log_time
    def start_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Start one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Convert IDs back to hashes
        hashes = self._ids_to_hashes(torrent_ids)
        self.client.torrents.resume(torrent_hashes=hashes)

    @log_time
    def stop_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Stop one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Convert IDs back to hashes
        hashes = self._ids_to_hashes(torrent_ids)
        self.client.torrents.pause(torrent_hashes=hashes)

    @log_time
    def remove_torrent(self, torrent_ids: int | str | list[int | str], delete_data: bool = False) -> None:
        """Remove one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Convert IDs back to hashes
        hashes = self._ids_to_hashes(torrent_ids)
        self.client.torrents.delete(delete_files=delete_data, torrent_hashes=hashes)

    @log_time
    def verify_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Verify one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Convert IDs back to hashes
        hashes = self._ids_to_hashes(torrent_ids)
        self.client.torrents.recheck(torrent_hashes=hashes)

    @log_time
    def reannounce_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        """Reannounce one or more torrents to their trackers."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Convert IDs back to hashes
        hashes = self._ids_to_hashes(torrent_ids)
        self.client.torrents.reannounce(torrent_hashes=hashes)

    @log_time
    def start_all_torrents(self) -> None:
        """Start all torrents."""
        self.client.torrents.resume(torrent_hashes='all')

    @log_time
    def stop_all_torrents(self) -> None:
        """Stop all torrents."""
        self.client.torrents.pause(torrent_hashes='all')

    @log_time
    def update_labels(self, torrent_ids: int | str | list[int | str], labels: list[str]) -> None:
        """Update labels/tags for one or more torrents."""
        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        # Convert IDs back to hashes
        hashes = self._ids_to_hashes(torrent_ids)

        # Convert labels list to comma-separated string for qBittorrent
        tags_str = ','.join(labels) if labels else ''

        for hash_str in hashes:
            # Get current torrent to find existing tags
            torrents = self.client.torrents.info(torrent_hashes=hash_str)
            if torrents:
                existing_tags = torrents[0].tags
                # If there are existing tags, remove them first
                if existing_tags:
                    try:
                        self.client.torrents_delete_tags(tags=existing_tags, torrent_hashes=hash_str)
                    except Exception:
                        pass  # Ignore if tag removal fails

            # Add new tags
            if tags_str:
                try:
                    self.client.torrents_add_tags(tags=tags_str, torrent_hashes=hash_str)
                except Exception:
                    pass  # Ignore if tag addition fails

    @log_time
    def toggle_alt_speed(self) -> bool:
        """Toggle alternative speed limits."""
        current_state = self.client.transfer.speed_limits_mode
        # Toggle: '0' = normal, '1' = alternative (API returns strings)
        new_state = '0' if current_state == '1' else '1'
        self.client.transfer.set_speed_limits_mode(mode=new_state)
        return new_state == '1'

    @log_time
    def has_separate_id(self) -> bool:
        """qBittorrent uses hash as ID, no separate ID field."""
        return False

    @log_time
    def _ids_to_hashes(self, ids: list[int | str]) -> list[str]:
        """Convert torrent IDs to qBittorrent hashes."""
        # For qBittorrent, IDs are already hash strings
        return [str(id) for id in ids]
