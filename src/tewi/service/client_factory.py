"""Factory for creating torrent client instances."""

from ..util.decorator import log_time
from .base_client import BaseClient, ClientError
from .transmission_client import TransmissionClient
from .qbittorrent_client import QBittorrentClient
from .deluge_client import DelugeClient


@log_time
def create_client(
    client_type: str,
    host: str,
    port: str,
    username: str = None,
    password: str = None
) -> BaseClient:
    """Create a torrent client instance based on the specified type.

    Args:
        client_type: Type of client ('transmission', 'qbittorrent', 'deluge')
        host: The hostname or IP address of the daemon
        port: The port number as a string
        username: Optional authentication username
        password: Optional authentication password

    Returns:
        BaseClient instance (TransmissionClient, QBittorrentClient,
        or DelugeClient)

    Raises:
        ClientError: If client_type is invalid or connection fails
    """
    client_type = client_type.lower()

    if client_type == 'transmission':
        return TransmissionClient(
            host=host,
            port=port,
            username=username,
            password=password
        )
    elif client_type == 'qbittorrent':
        return QBittorrentClient(
            host=host,
            port=port,
            username=username,
            password=password
        )
    elif client_type == 'deluge':
        return DelugeClient(
            host=host,
            port=port,
            username=username,
            password=password
        )
    else:
        raise ClientError(
            f"Invalid client type: '{client_type}'. "
            f"Supported types: 'transmission', 'qbittorrent', 'deluge'"
        )
