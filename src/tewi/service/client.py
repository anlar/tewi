from typing import TypedDict

from transmission_rpc import Client as TransmissionClient


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
