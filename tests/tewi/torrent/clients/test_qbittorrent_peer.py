# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for conversion of qBittorrent peers."""

import pytest
from qbittorrentapi.definitions import Dictionary

from src.tewi.torrent.clients.qbittorrent import QBittorrentClient


def make_peer(connection: str | None, flags: str) -> Dictionary:
    """Peer as returned by qBittorrent Web API (sync/torrentPeers)."""
    return Dictionary(
        {
            "ip": "192.0.2.1",
            "port": 51413,
            "client": "Transmission 4.0.0",
            "progress": 0.5,
            "dl_speed": 0,
            "up_speed": 0,
            "connection": connection,
            "flags": flags,
            "country": "",
        }
    )


@pytest.mark.parametrize(
    "connection,flags,expected",
    [
        # qBittorrent flags: E = encrypted traffic, e = encrypted
        # handshake (plain data after it), P = uTP
        ("BT", "D E", True),
        ("BT", "D e", False),
        ("BT", "D", False),
        # uTP is transport protocol, not encryption ("μTP" with Greek mu)
        ("μTP", "D P", False),
        ("μTP", "D E P", True),
        # Unknown connection type doesn't fail conversion
        (None, "D", False),
    ],
)
def test_peer_encryption(connection, flags, expected):
    client = object.__new__(QBittorrentClient)

    peer = client._peer_to_dto(make_peer(connection, flags))

    assert peer.is_encrypted is expected
