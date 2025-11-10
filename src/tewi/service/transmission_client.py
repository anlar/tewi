"""Transmission torrent client implementation."""

import os
import pathlib

from dataclasses import replace

from transmission_rpc import Torrent
from transmission_rpc import Client as TransmissionRPCClient

from ..util.misc import is_torrent_link
from ..common import SortOrder, TorrentDTO, TorrentDetailDTO, FileDTO, PeerDTO, TrackerDTO
from .base_client import BaseClient, ClientMeta, ClientStats, ClientSession


class TransmissionClient(BaseClient):

    def __init__(self,
                 host: str, port: str,
                 username: str = None, password: str = None):

        self.client = TransmissionRPCClient(host=host,
                                            port=port,
                                            username=username,
                                            password=password)

    def meta(self) -> ClientMeta:
        return {
                'name': 'Transmission',
                'version': self.client.get_session().version
        }

    def stats(self) -> ClientStats:
        s = self.client.session_stats()

        current_ratio = (
                float('inf')
                if s.current_stats.downloaded_bytes == 0 else
                s.current_stats.uploaded_bytes / s.current_stats.downloaded_bytes
        )

        total_ratio = (
                float('inf')
                if s.cumulative_stats.downloaded_bytes == 0 else
                s.cumulative_stats.uploaded_bytes / s.cumulative_stats.downloaded_bytes
        )

        return {
                'current_uploaded_bytes': s.current_stats.uploaded_bytes,
                'current_downloaded_bytes': s.current_stats.downloaded_bytes,
                'current_ratio': current_ratio,
                'current_active_seconds': s.current_stats.seconds_active,
                'total_uploaded_bytes': s.cumulative_stats.uploaded_bytes,
                'total_downloaded_bytes': s.cumulative_stats.downloaded_bytes,
                'total_ratio': total_ratio,
                'total_active_seconds': s.cumulative_stats.seconds_active,
                'total_started_count': s.cumulative_stats.session_count,
        }

    def session(self, torrents: list[TorrentDTO], sort_order: SortOrder, sort_order_asc: bool) -> ClientSession:
        s = self.client.get_session()
        stats = self.client.session_stats()

        torrents_down = len([x for x in torrents if x.status == 'downloading'])
        torrents_seed = len([x for x in torrents if x.status == 'seeding'])
        torrents_check = len([x for x in torrents if x.status == 'checking'])

        return {
                'download_dir': s.download_dir,
                'download_dir_free_space': s.download_dir_free_space,
                'upload_speed': stats.upload_speed,
                'download_speed': stats.download_speed,
                'alt_speed_enabled': s.alt_speed_enabled,
                'alt_speed_up': s.alt_speed_up,
                'alt_speed_down': s.alt_speed_down,

                'torrents_complete_size': sum(t.size_when_done - t.left_until_done for t in torrents),
                'torrents_total_size': sum(t.size_when_done for t in torrents),

                'torrents_count': len(torrents),
                'torrents_down': torrents_down,
                'torrents_seed': torrents_seed,
                'torrents_check': torrents_check,
                'torrents_stop': len(torrents) - torrents_down - torrents_seed - torrents_check,

                'sort_order': sort_order,
                'sort_order_asc': sort_order_asc,
        }

    def preferences(self) -> dict[str, str]:
        session_dict = self.client.get_session().fields

        filtered = {k: v for k, v in session_dict.items() if not k.startswith(tuple(['units', 'version']))}

        return dict(sorted(filtered.items()))

    def _torrent_to_dto(self, torrent: Torrent) -> TorrentDTO:
        """Convert transmission-rpc Torrent to TorrentDTO."""
        return TorrentDTO(
            id=torrent.id,
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
            labels=list(torrent.labels) if torrent.labels else [],
        )

    def _file_to_dto(self, file) -> FileDTO:
        """Convert transmission-rpc File to FileDTO."""
        return FileDTO(
            id=file.id,
            name=file.name,
            size=file.size,
            completed=file.completed,
            selected=file.selected,
            priority=file.priority,
        )

    def _peer_to_dto(self, peer: dict) -> PeerDTO:
        """Convert transmission-rpc peer dict to PeerDTO."""
        return PeerDTO(
            address=peer["address"],
            client_name=peer["clientName"],
            progress=peer["progress"],
            is_encrypted=peer["isEncrypted"],
            rate_to_client=peer["rateToClient"],
            rate_to_peer=peer["rateToPeer"],
            flag_str=peer["flagStr"],
        )

    def _tracker_to_dto(self, tracker) -> TrackerDTO:
        """Convert transmission-rpc Tracker to TrackerDTO."""
        # Map announce_state to readable status
        # 0 = inactive, 1 = waiting, 2 = queued, 3 = active
        announce_state_map = {
            0: "Inactive",
            1: "Waiting",
            2: "Queued",
            3: "Active"
        }
        status = announce_state_map.get(tracker.announce_state, "Unknown")

        # Use last_announce_result for message, fallback to empty string
        message = tracker.last_announce_result if tracker.last_announce_result else ""

        # Get peer count from last announce
        peer_count = tracker.last_announce_peer_count if tracker.last_announce_peer_count >= 0 else -1

        return TrackerDTO(
            host=tracker.host,
            tier=tracker.tier,
            seeder_count=tracker.seeder_count,
            leecher_count=tracker.leecher_count,
            download_count=tracker.download_count,
            status=status,
            message=message,
            peer_count=peer_count,
        )

    def _torrent_detail_to_dto(self, torrent: Torrent) -> TorrentDetailDTO:
        """Convert transmission-rpc Torrent to TorrentDetailDTO."""
        files = [self._file_to_dto(f) for f in torrent.get_files()]
        peers = [self._peer_to_dto(p) for p in torrent.peers]
        trackers = [self._tracker_to_dto(t) for t in torrent.tracker_stats]

        return TorrentDetailDTO(
            id=torrent.id,
            name=torrent.name,
            hash_string=torrent.hash_string,
            total_size=torrent.total_size,
            piece_count=torrent.piece_count,
            piece_size=torrent.piece_size,
            is_private=torrent.is_private,
            comment=torrent.comment if torrent.comment else "",
            creator=torrent.creator if torrent.creator else "",
            labels=list(torrent.labels) if torrent.labels else [],
            status=torrent.status,
            download_dir=torrent.download_dir,
            downloaded_ever=torrent.downloaded_ever,
            uploaded_ever=torrent.uploaded_ever,
            ratio=torrent.ratio,
            error_string=torrent.error_string if torrent.error_string else "",
            added_date=torrent.added_date,
            start_date=torrent.start_date,
            done_date=torrent.done_date,
            activity_date=torrent.activity_date,
            peers_connected=torrent.peers_connected,
            peers_sending_to_us=torrent.peers_sending_to_us,
            peers_getting_from_us=torrent.peers_getting_from_us,
            files=files,
            peers=peers,
            trackers=trackers,
        )

    def torrents(self) -> list[TorrentDTO]:
        torrents = self.client.get_torrents(
                arguments=['id', 'name', 'status', 'totalSize', 'left_until_done',
                           'percentDone', 'eta', 'rateUpload', 'rateDownload',
                           'uploadRatio', 'sizeWhenDone', 'leftUntilDone',
                           'addedDate', 'activityDate', 'queuePosition',
                           'peersConnected', 'peersGettingFromUs',
                           'peersSendingToUs', 'bandwidthPriority', 'uploadedEver',
                           'labels']
                )
        return [self._torrent_to_dto(t) for t in torrents]

    def torrents_test(self) -> list[TorrentDTO]:
        torrents = self.torrents()

        result = []

        idx = 1

        for i in range(50):
            for t in torrents:
                t_copy = replace(t, id=idx, name=t.name + "-" + str(idx))
                result.append(t_copy)
                idx = idx + 1

        return result

    def torrent(self, id: int | str) -> TorrentDetailDTO:
        """Get detailed information about a specific torrent."""
        torrent = self.client.get_torrent(id)
        return self._torrent_detail_to_dto(torrent)

    def add_torrent(self, value: str) -> None:
        if is_torrent_link(value):
            self.client.add_torrent(value)
        else:
            file = os.path.expanduser(value)
            self.client.add_torrent(pathlib.Path(file))

    def start_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        self.client.start_torrent(torrent_ids)

    def stop_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        self.client.stop_torrent(torrent_ids)

    def remove_torrent(self,
                       torrent_ids: int | str | list[int | str],
                       delete_data: bool = False) -> None:

        self.client.remove_torrent(torrent_ids,
                                   delete_data=delete_data)

    def verify_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        self.client.verify_torrent(torrent_ids)

    def reannounce_torrent(self, torrent_ids: int | str | list[int | str]) -> None:
        self.client.reannounce_torrent(torrent_ids)

    def start_all_torrents(self) -> None:
        self.client.start_all()

    def stop_all_torrents(self) -> None:
        torrents = self.client.get_torrents(arguments=['id'])
        self.stop_torrent([t.id for t in torrents])

    def update_labels(self,
                      torrent_ids: int | str | list[int | str],
                      labels: list[str]) -> None:

        if isinstance(torrent_ids, (int, str)):
            torrent_ids = [torrent_ids]

        self.client.change_torrent(torrent_ids,
                                   labels=labels)

    def toggle_alt_speed(self) -> bool:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled=not alt_speed_enabled)
        return not alt_speed_enabled

    def has_separate_id(self) -> bool:
        """Transmission uses integer IDs separate from hash."""
        return True
