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

from src.tewi.torrent.clients.transmission import TransmissionClient
from src.tewi.torrent.factory import create_client
from src.tewi.torrent.models import ClientError


class TestCreateClient:
    """Test cases for create_client factory function."""

    def test_create_transmission_client(self, request):
        """Test creating a Transmission client.

        Requires Transmission daemon running on localhost.
        Can be started with: make docker-up docker-init
        """
        # Get port from pytest config
        port = request.config.getoption("--transmission-port")

        # Call factory to create real client
        result = create_client(
            client_type="transmission",
            host="localhost",
            port=port,
        )

        # Verify result is TransmissionClient instance
        assert isinstance(result, TransmissionClient)

        # Verify client can connect and retrieve metadata
        meta = result.meta()
        assert meta["name"] == "Transmission"
        assert isinstance(meta["version"], str)

    def test_create_unknown_client(self):
        """Test creating an unknown client type raises ClientError."""
        with pytest.raises(ClientError) as exc_info:
            create_client(
                client_type="unknown",
                host="localhost",
                port="9092",
            )

        # Verify error message
        error_message = str(exc_info.value)
        assert "Invalid client type: 'unknown'" in error_message
        assert "transmission" in error_message
        assert "qbittorrent" in error_message
        assert "deluge" in error_message
