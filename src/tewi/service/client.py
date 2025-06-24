import os
import pathlib

from typing import TypedDict

from transmission_rpc import Torrent
from transmission_rpc import Client as TransmissionClient

from ..util.misc import is_torrent_link


class ClientMeta(TypedDict):
    name: str
    version: str


class ClientStats(TypedDict):
    current_uploaded_bytes: int
    current_downloaded_bytes: int
    current_ratio: float
    current_active_seconds: int

    total_uploaded_bytes: int
    total_downloaded_bytes: int
    total_ratio: float
    total_active_seconds: int
    total_started_count: int


class Client:

    def __init__(self,
                 host: str, port: str,
                 username: str = None, password: str = None):

        self.client = TransmissionClient(host=host,
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

    def preferences(self) -> dict[str, str]:
        session_dict = self.client.get_session().fields

        filtered = {k: v for k, v in session_dict.items() if not k.startswith(tuple(['units', 'version']))}

        return dict(sorted(filtered.items()))

    def torrents(self) -> list[Torrent]:
        return self.client.get_torrents(
                arguments=['id', 'name', 'status', 'totalSize', 'left_until_done',
                           'percentDone', 'eta', 'rateUpload', 'rateDownload',
                           'uploadRatio', 'sizeWhenDone', 'leftUntilDone',
                           'addedDate', 'peersConnected', 'peersGettingFromUs',
                           'peersSendingToUs', 'bandwidthPriority', 'uploadedEver',
                           'labels']
                )

    def torrent(self, id: int) -> Torrent:
        return self.client.get_torrent(id)

    def add_torrent(self, value: str) -> None:
        if is_torrent_link(value):
            self.client.add_torrent(value)
        else:
            file = os.path.expanduser(value)
            self.client.add_torrent(pathlib.Path(file))

    def start_torrent(self, torrent_ids: int | list[int]) -> None:
        self.client.start_torrent(torrent_ids)

    def stop_torrent(self, torrent_ids: int | list[int]) -> None:
        self.client.stop_torrent(torrent_ids)

    def remove_torrent(self,
                       torrent_ids: int | list[int],
                       delete_data: bool = False) -> None:

        self.client.remove_torrent(torrent_ids,
                                   delete_data=delete_data)

    def verify_torrent(self, torrent_ids: int | list[int]) -> None:
        self.client.verify_torrent(torrent_ids)

    def reannounce_torrent(self, torrent_ids: int | list[int]) -> None:
        self.client.reannounce_torrent(torrent_ids)

    def start_all_torrents(self) -> None:
        self.client.start_all()

    def update_labels(self,
                      torrent_ids: int | list[int],
                      labels: list[str]) -> None:

        if isinstance(torrent_ids, int):
            torrent_ids = [torrent_ids]

        self.client.change_torrent(torrent_ids,
                                   labels=labels)

    def toggle_alt_speed(self) -> bool:
        alt_speed_enabled = self.client.get_session().alt_speed_enabled
        self.client.set_session(alt_speed_enabled=not alt_speed_enabled)
        return not alt_speed_enabled
