"""Factory for creating torrent client instances."""

from ..util.log import log_time
from .base import BaseClient, ClientCapability
from .clients.deluge import DelugeClient
from .clients.qbittorrent import QBittorrentClient
from .clients.transmission import TransmissionClient
from .models import ClientError

# Re-export for convenience
__all__ = ["create_client", "ClientCapability"]


@log_time
def create_client(
    client_type: str,
    host: str,
    port: str,
    username: str | None = None,
    password: str | None = None,
    path: str | None = None,
) -> BaseClient:
    """Create a torrent client instance based on the specified type.

    Args:
        client_type: Type of client ('transmission', 'qbittorrent', 'deluge')
        host: The hostname or IP address of the daemon
        port: The port number as a string
        username: Optional authentication username
        password: Optional authentication password
        path: Optional RPC path for Transmission or base JSON path for Deluge

    Returns:
        BaseClient instance (TransmissionClient, QBittorrentClient,
        or DelugeClient)

    Raises:
        ClientError: If client_type is invalid or connection fails
    """
    client_type = client_type.lower()

    if client_type == "transmission":
        return TransmissionClient(
            host=host,
            port=port,
            path=path,
            username=username,
            password=password,
        )
    elif client_type == "qbittorrent":
        return QBittorrentClient(
            host=host, port=port, username=username, password=password
        )
    elif client_type == "deluge":
        return DelugeClient(
            host=host,
            port=port,
            path=path,
            username=username,
            password=password,
        )
    else:
        raise ClientError(
            f"Invalid client type: '{client_type}'. "
            f"Supported types: 'transmission', 'qbittorrent', 'deluge'"
        )
