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

import configparser

from src.tewi.config import (
    _load_client_section,
    _load_debug_section,
    _load_ui_section,
)


class TestLoadClientSection:
    """Test cases for _load_client_section function."""

    def test_empty_config(self):
        """Test handling of empty config without [client] section."""
        config_text = ""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        assert config == {}

    def test_empty_section(self):
        """Test handling of [client] section with all empty values."""
        config_text = """
[client]
type =
host =
port =
username =
password =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        assert config == {}

    def test_filled_values(self):
        """Test handling of [client] section with all values filled."""
        config_text = """
[client]
type = qbittorrent
host = 192.168.1.100
port = 8080
username = admin
password = secret123
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        assert config == {
            "client_type": "qbittorrent",
            "host": "192.168.1.100",
            "port": "8080",
            "username": "admin",
            "password": "secret123",
        }

    def test_partial_values(self):
        """Test handling of [client] section with some values filled."""
        config_text = """
[client]
type = transmission
host = localhost
port =
username =
password =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        assert config == {"client_type": "transmission", "host": "localhost"}

    def test_missing_options(self):
        """Test handling when some options are not present at all."""
        config_text = """
[client]
type = transmission
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        assert config == {"client_type": "transmission"}

    def test_whitespace_only_values(self):
        """Test handling of whitespace-only values."""
        config_text = """
[client]
type =
host = localhost
port =   \t
username =
password =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        # Only host should be included, whitespace-only treated as empty
        assert config == {"host": "localhost"}

    def test_trimming_whitespace(self):
        """Test that values are trimmed from left/right whitespace."""
        config_text = """
[client]
type =  transmission
host =   localhost
port = 9091
username =  admin
password = secret123
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_client_section(parser, config)

        # All values should be trimmed
        assert config == {
            "client_type": "transmission",
            "host": "localhost",
            "port": "9091",
            "username": "admin",
            "password": "secret123",
        }


class TestLoadUiSection:
    """Test cases for _load_ui_section function."""

    def test_empty_config(self):
        """Test handling of empty config without [ui] section."""
        config_text = ""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {}

    def test_empty_section(self):
        """Test handling of [ui] section with all empty values."""
        config_text = """
[ui]
view_mode =
page_size =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {}

    def test_filled_values(self):
        """Test handling of [ui] section with all values filled."""
        config_text = """
[ui]
view_mode = compact
page_size = 50
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"view_mode": "compact", "page_size": 50}

    def test_partial_values_view_mode_only(self):
        """Test with only view_mode filled."""
        config_text = """
[ui]
view_mode = oneline
page_size =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"view_mode": "oneline"}

    def test_partial_values_page_size_only(self):
        """Test with only page_size filled."""
        config_text = """
[ui]
view_mode =
page_size = 25
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"page_size": 25}

    def test_invalid_page_size(self, capsys):
        """Test handling of invalid page_size value."""
        config_text = """
[ui]
view_mode = card
page_size = invalid
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # Should only include view_mode, page_size should be skipped
        assert config == {"view_mode": "card"}
        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning: Invalid page_size value in config" in captured.err

    def test_whitespace_only_values(self):
        """Test handling of whitespace-only values."""
        config_text = """
[ui]
view_mode =   \t\n
page_size =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # Whitespace-only values should be treated as None
        assert config == {}

    def test_trimming_whitespace(self):
        """Test that values are trimmed from left/right whitespace."""
        config_text = """
[ui]
view_mode =  compact
page_size =   50
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # All values should be trimmed
        assert config == {"view_mode": "compact", "page_size": 50}

    def test_with_refresh_interval(self):
        """Test ui section with refresh_interval."""
        config_text = """
[ui]
view_mode = card
page_size = 30
refresh_interval = 10
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {
            "view_mode": "card",
            "page_size": 30,
            "refresh_interval": 10,
        }

    def test_with_limit_torrents(self):
        """Test ui section with limit_torrents."""
        config_text = """
[ui]
view_mode = compact
page_size = 50
limit_torrents = 100
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {
            "view_mode": "compact",
            "page_size": 50,
            "limit_torrents": 100,
        }

    def test_with_all_options(self):
        """Test ui section with all options including behavior options."""
        config_text = """
[ui]
view_mode = oneline
page_size = 25
refresh_interval = 15
limit_torrents = 50
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {
            "view_mode": "oneline",
            "page_size": 25,
            "refresh_interval": 15,
            "limit_torrents": 50,
        }

    def test_invalid_refresh_interval(self, capsys):
        """Test handling of invalid refresh_interval value."""
        config_text = """
[ui]
view_mode = card
refresh_interval = not_a_number
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # Should only include view_mode
        assert config == {"view_mode": "card"}
        # Check that warning was printed
        captured = capsys.readouterr()
        assert (
            "Warning: Invalid refresh_interval value in config" in captured.err
        )

    def test_invalid_limit_torrents(self, capsys):
        """Test handling of invalid limit_torrents value."""
        config_text = """
[ui]
page_size = 30
limit_torrents = abc
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # Should only include page_size
        assert config == {"page_size": 30}
        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning: Invalid limit_torrents value in config" in captured.err

    def test_badge_options(self):
        """Test ui section with badge display options."""
        config_text = """
[ui]
badge_max_count = 2
badge_max_length = 10
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"badge_max_count": 2, "badge_max_length": 10}

    def test_badge_options_unlimited_count(self):
        """Test badge_max_count with unlimited (-1)."""
        config_text = """
[ui]
badge_max_count = -1
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"badge_max_count": -1}

    def test_badge_options_no_badges(self):
        """Test badge_max_count with no badges (0)."""
        config_text = """
[ui]
badge_max_count = 0
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"badge_max_count": 0}

    def test_badge_options_unlimited_length(self):
        """Test badge_max_length with unlimited (0)."""
        config_text = """
[ui]
badge_max_length = 0
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        assert config == {"badge_max_length": 0}

    def test_invalid_badge_max_count(self, capsys):
        """Test handling of invalid badge_max_count value."""
        config_text = """
[ui]
view_mode = card
badge_max_count = invalid
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # Should only include view_mode
        assert config == {"view_mode": "card"}
        # Check that warning was printed
        captured = capsys.readouterr()
        assert (
            "Warning: Invalid badge_max_count value in config" in captured.err
        )

    def test_invalid_badge_max_length(self, capsys):
        """Test handling of invalid badge_max_length value."""
        config_text = """
[ui]
view_mode = card
badge_max_length = abc
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_ui_section(parser, config)

        # Should only include view_mode
        assert config == {"view_mode": "card"}
        # Check that warning was printed
        captured = capsys.readouterr()
        assert (
            "Warning: Invalid badge_max_length value in config" in captured.err
        )


class TestLoadDebugSection:
    """Test cases for _load_debug_section function."""

    def test_empty_config(self):
        """Test handling of empty config without [debug] section."""
        config_text = ""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        assert config == {}

    def test_empty_section(self):
        """Test handling of [debug] section with all empty values."""
        config_text = """
[debug]
log_level =
test_mode =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        assert config == {}

    def test_filled_values_debug(self):
        """Test handling of [debug] section with log_level=debug."""
        config_text = """
[debug]
log_level = debug
test_mode = 1
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        assert config == {"log_level": "debug", "test_mode": 1}

    def test_filled_values_warning(self):
        """Test handling of [debug] section with log_level=warning."""
        config_text = """
[debug]
log_level = warning
test_mode = 0
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        assert config == {"log_level": "warning", "test_mode": 0}

    def test_partial_values_log_level_only(self):
        """Test with only log_level filled."""
        config_text = """
[debug]
log_level = info
test_mode =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        assert config == {"log_level": "info"}

    def test_partial_values_test_mode_only(self):
        """Test with only test_mode filled."""
        config_text = """
[debug]
log_level =
test_mode = 2
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        assert config == {"test_mode": 2}

    def test_log_level_variations(self):
        """Test various log level value formats."""
        # Test 'error'
        config_text = """
[debug]
log_level = error
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}
        _load_debug_section(parser, config)
        assert config == {"log_level": "error"}

        # Test 'critical'
        config_text = """
[debug]
log_level = critical
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}
        _load_debug_section(parser, config)
        assert config == {"log_level": "critical"}

        # Test 'info'
        config_text = """
[debug]
log_level = info
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}
        _load_debug_section(parser, config)
        assert config == {"log_level": "info"}

        # Test 'debug'
        config_text = """
[debug]
log_level = debug
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}
        _load_debug_section(parser, config)
        assert config == {"log_level": "debug"}

    def test_invalid_log_level_value(self):
        """Test handling of invalid log_level value."""
        config_text = """
[debug]
log_level = invalid_level
test_mode = 1
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        # Should include both values (no validation in config loading)
        assert config == {"log_level": "invalid_level", "test_mode": 1}

    def test_invalid_test_mode_value(self, capsys):
        """Test handling of invalid test_mode value."""
        config_text = """
[debug]
log_level = info
test_mode = invalid
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        # Should only include log_level
        assert config == {"log_level": "info"}
        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning: Invalid test_mode value in config" in captured.err

    def test_whitespace_only_values(self):
        """Test handling of whitespace-only values."""
        config_text = """
[debug]
log_level =
test_mode =
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        # Whitespace-only values should be treated as None
        assert config == {}

    def test_trimming_whitespace(self):
        """Test that values are trimmed from left/right whitespace."""
        config_text = """
[debug]
log_level =  warning
test_mode =   2
"""
        parser = configparser.ConfigParser()
        parser.read_string(config_text)
        config = {}

        _load_debug_section(parser, config)

        # All values should be trimmed
        assert config == {"log_level": "warning", "test_mode": 2}
