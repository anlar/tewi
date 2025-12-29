#!/usr/bin/env python3

# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2024  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import pytest

from src.tewi.torrent.base import ClientCapability
from src.tewi.torrent.clients.transmission import TransmissionClient


@pytest.fixture(scope="module")
def client(request):
    """Create TransmissionClient instance for all tests.

    Port can be configured with --transmission-port option.
    Default port: 9070 (docker setup)

    Requires Transmission daemon running on localhost.
    Can be started with: make docker-up docker-init
    """
    port = request.config.getoption("--transmission-port")
    return TransmissionClient(host="localhost", port=port)


@pytest.mark.integration
class TestTransmissionClientLifecycle:
    """Test TransmissionClient lifecycle and metadata methods."""

    def test_init(self, client):
        """Test TransmissionClient initialization."""
        assert client is not None
        assert isinstance(client, TransmissionClient)

    def test_capable_category(self, client):
        """Test that Transmission doesn't support categories."""
        result = client.capable(ClientCapability.CATEGORY)
        assert isinstance(result, bool)
        assert result is False

    def test_capable_label(self, client):
        """Test that Transmission supports labels."""
        result = client.capable(ClientCapability.LABEL)
        assert isinstance(result, bool)
        assert result is True

    def test_capable_toggle_alt_speed(self, client):
        """Test that Transmission supports alt speed toggling."""
        result = client.capable(ClientCapability.TOGGLE_ALT_SPEED)
        assert isinstance(result, bool)
        assert result is True

    def test_capable_set_priority(self, client):
        """Test that Transmission supports priority setting."""
        result = client.capable(ClientCapability.SET_PRIORITY)
        assert isinstance(result, bool)
        assert result is True

    def test_capable_torrent_id(self, client):
        """Test that Transmission uses numeric torrent IDs."""
        result = client.capable(ClientCapability.TORRENT_ID)
        assert isinstance(result, bool)
        assert result is True

    def test_meta(self, client):
        """Test retrieving daemon metadata."""
        meta = client.meta()

        # Check type
        assert isinstance(meta, dict)

        # Check structure (ClientMeta TypedDict)
        assert "name" in meta
        assert "version" in meta

        # Check values
        assert meta["name"] == "Transmission"
        assert isinstance(meta["version"], str)
        assert len(meta["version"]) > 0


@pytest.mark.integration
class TestTransmissionClientSession:
    """Test TransmissionClient session methods."""

    def test_session(self, client):
        """Test retrieving session information."""
        # Get torrents first (required for session counts)
        torrents = client.torrents()

        session = client.session(torrents)

        # Check type
        assert isinstance(session, dict)

        # Check ClientSession required fields
        required_fields = [
            "download_dir",
            "download_dir_free_space",
            "upload_speed",
            "download_speed",
            "alt_speed_enabled",
            "alt_speed_up",
            "alt_speed_down",
            "torrents_complete_size",
            "torrents_total_size",
            "torrents_count",
            "torrents_down",
            "torrents_seed",
            "torrents_check",
            "torrents_stop",
        ]

        for field in required_fields:
            assert field in session, f"Missing field: {field}"

        # Basic type checks
        assert isinstance(session["download_dir"], str)
        assert isinstance(session["alt_speed_enabled"], bool)
        assert isinstance(session["torrents_count"], int)

    def test_stats(self, client):
        """Test retrieving session statistics."""
        stats = client.stats()

        # Check type
        assert isinstance(stats, dict)

        # Check some ClientStats fields (some may be None)
        assert "current_uploaded_bytes" in stats
        assert "current_downloaded_bytes" in stats
        assert "current_ratio" in stats
        assert "total_uploaded_bytes" in stats
        assert "total_downloaded_bytes" in stats
        assert "total_ratio" in stats

        # Transmission-specific: these should have values (not None)
        assert isinstance(stats["current_uploaded_bytes"], int)
        assert isinstance(stats["current_downloaded_bytes"], int)

    def test_preferences(self, client):
        """Test retrieving session preferences."""
        prefs = client.preferences()

        # Check type
        assert isinstance(prefs, dict)

        # Should have multiple preferences
        assert len(prefs) > 0

        # All keys should be strings
        for key in prefs.keys():
            assert isinstance(key, str)

    def test_toggle_alt_speed(self, client):
        """Test toggling alternative speed limits."""
        # Get initial state
        initial_session = client.session(client.torrents())
        initial_state = initial_session["alt_speed_enabled"]

        # Toggle once
        result1 = client.toggle_alt_speed()
        assert isinstance(result1, bool)
        assert result1 == (not initial_state)

        # Verify state changed
        session_after_toggle = client.session(client.torrents())
        assert session_after_toggle["alt_speed_enabled"] == result1

        # Toggle back to restore original state
        result2 = client.toggle_alt_speed()
        assert result2 == initial_state

        # Verify restored
        final_session = client.session(client.torrents())
        assert final_session["alt_speed_enabled"] == initial_state


@pytest.mark.integration
class TestTransmissionClientTorrents:
    """Test TransmissionClient torrent retrieval."""

    def test_torrents(self, client):
        """Test retrieving torrent list."""
        torrents = client.torrents()

        # Check type
        assert isinstance(torrents, list)

        # If torrents exist (depends on docker-init)
        if len(torrents) > 0:
            # Check first torrent is Torrent
            first = torrents[0]

            # Check required Torrent fields
            assert hasattr(first, "id")
            assert hasattr(first, "name")
            assert hasattr(first, "status")
            assert hasattr(first, "total_size")

            # Check types
            assert isinstance(first.id, int)
            assert isinstance(first.name, str)
            assert isinstance(first.status, str)
            assert isinstance(first.total_size, int)
