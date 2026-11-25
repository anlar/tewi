# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for v1 info hash of qBittorrent torrents, used in magnet links."""

import pytest
from qbittorrentapi import TorrentDictionary

from src.tewi.torrent.clients.qbittorrent import QBittorrentClient

V1 = "a" * 40
# Truncated v2 info hash, used by qBittorrent as torrent ID
V2_TRUNCATED = "b" * 40


@pytest.mark.parametrize(
    "data,expected",
    [
        # v1 torrent
        ({"hash": V1, "infohash_v1": V1}, V1),
        # Hybrid torrent: ID is truncated v2 info hash
        ({"hash": V2_TRUNCATED, "infohash_v1": V1}, V1),
        # v2-only torrent has no v1 info hash
        ({"hash": V2_TRUNCATED, "infohash_v1": ""}, None),
        # qBittorrent before 4.4 supports only v1 torrents
        ({"hash": V1}, V1),
    ],
    ids=["v1", "hybrid", "v2-only", "old-qbittorrent"],
)
def test_hash_v1(data, expected):
    torrent = TorrentDictionary(data, client=None)

    assert QBittorrentClient._hash_v1(torrent) == expected
