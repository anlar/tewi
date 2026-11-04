"""Factory for creating torrent client instances."""

import os
from dataclasses import replace

import urllib3

from ..util.log import get_logger, log_time
from .base import BaseClient, ClientCapability
from .clients.deluge import DelugeClient
from .clients.qbittorrent import QBittorrentClient
from .clients.rtorrent import RTorrentClient
from .clients.transmission import TransmissionClient
from .models import ClientError, TlsOptions
from .util import is_loopback

# Re-export for convenience
__all__ = [
    "create_client",
    "split_host_scheme",
    "ClientCapability",
    "TlsOptions",
]

logger = get_logger()


def split_host_scheme(host: str, tls: TlsOptions) -> tuple[str, TlsOptions]:
    """Split optional "http://" or "https://" prefix from host.

    Scheme in host takes priority over `tls.enabled`, so "https://nas"
    can be used as a shortcut for enabling TLS.

    Raises:
        ClientError: If host has unsupported scheme
    """
    scheme, sep, rest = host.partition("://")
    if not sep:
        return host, tls

    scheme = scheme.lower()
    if scheme not in ("http", "https"):
        raise ClientError(
            f"Unsupported scheme in host: {scheme} (use http or https)"
        )
    return rest.rstrip("/"), replace(tls, enabled=scheme == "https")


@log_time
def create_client(
    client_type: str,
    host: str,
    port: str,
    username: str | None = None,
    password: str | None = None,
    path: str | None = None,
    tls: TlsOptions | None = None,
) -> BaseClient:
    """Create a torrent client instance based on the specified type.

    Args:
        client_type: Type of client ('transmission', 'qbittorrent',
            'deluge', 'rtorrent')
        host: The hostname or IP address of the daemon
        port: The port number as a string
        username: Optional authentication username
        password: Optional authentication password
        path: Optional RPC path for Transmission, base JSON path for Deluge
            or XML-RPC path for rTorrent over HTTP (SCGI is used if not set)
        tls: Optional TLS settings (plain HTTP is used if not set). Host
            with "https://" or "http://" prefix overrides `tls.enabled`.

    Returns:
        BaseClient instance (TransmissionClient, QBittorrentClient,
        DelugeClient or RTorrentClient)

    Raises:
        ClientError: If client_type is invalid or connection fails
    """
    client_type = client_type.lower()

    host, tls = split_host_scheme(host, tls or TlsOptions())

    if tls.ca_cert:
        ca_cert = os.path.expanduser(tls.ca_cert)
        if not os.path.isfile(ca_cert):
            raise ClientError(f"CA certificate file not found: {ca_cert}")
        tls = replace(tls, ca_cert=ca_cert)

    if tls.enabled and not tls.verify:
        logger.warning(
            "TLS certificate verification is disabled: connection to "
            f"{host} isn't protected from interception"
        )
        # Warning is logged above once, urllib3 would print it on every
        # request to stderr, breaking UI
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    elif not tls.enabled and password and not is_loopback(host):
        # qBittorrent may still switch to HTTPS if daemon requires it
        logger.warning(
            f"Connecting to {host} without TLS: password may be sent "
            "unencrypted (enable tls option or use SSH tunnel or VPN)"
        )

    if client_type == "transmission":
        return TransmissionClient(
            host=host,
            port=port,
            path=path,
            username=username,
            password=password,
            tls=tls,
        )
    elif client_type == "qbittorrent":
        return QBittorrentClient(
            host=host,
            port=port,
            username=username,
            password=password,
            tls=tls,
        )
    elif client_type == "deluge":
        return DelugeClient(
            host=host,
            port=port,
            path=path,
            username=username,
            password=password,
            tls=tls,
        )
    elif client_type == "rtorrent":
        return RTorrentClient(
            host=host,
            port=port,
            path=path,
            username=username,
            password=password,
            tls=tls,
        )
    else:
        raise ClientError(
            f"Invalid client type: '{client_type}'. "
            f"Supported types: 'transmission', 'qbittorrent', 'deluge', "
            f"'rtorrent'"
        )
