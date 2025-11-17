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
import os
import sys
from pathlib import Path
from argparse import Namespace


def get_config_path() -> Path:
    """
    Get the configuration file path following XDG Base Directory spec.

    Returns path to tewi.conf in XDG_CONFIG_HOME or ~/.config if not set.
    """
    config_home = os.environ.get('XDG_CONFIG_HOME')
    if config_home:
        return Path(config_home) / 'tewi.conf'
    else:
        return Path.home() / '.config' / 'tewi.conf'


def _get_string_option(parser: configparser.ConfigParser,
                       section: str, option: str) -> str | None:
    """Get string option, returning None if empty or missing."""
    if parser.has_option(section, option):
        val = parser.get(section, option)
        # Return None if value is empty or contains only whitespace
        return val.strip() if val and val.strip() else None
    return None


def _get_int_option(parser: configparser.ConfigParser,
                    section: str, option: str) -> int | None:
    """Get int option, returning None if empty, missing, or invalid."""
    val = _get_string_option(parser, section, option)
    if val is not None:
        try:
            return int(val)
        except ValueError as e:
            print(f"Warning: Invalid {option} value in config: {e}",
                  file=sys.stderr)
    return None


def _get_bool_option(parser: configparser.ConfigParser,
                     section: str, option: str) -> bool | None:
    """Get bool option, returning None if missing or invalid."""
    if parser.has_option(section, option):
        value = parser.get(section, option)
        # Return None if value is empty or contains only whitespace
        if not value or not value.strip():
            return None
        try:
            return parser.getboolean(section, option)
        except ValueError as e:
            print(f"Warning: Invalid {option} value in config: {e}",
                  file=sys.stderr)
    return None


def _load_client_section(parser: configparser.ConfigParser,
                         config: dict) -> None:
    """Load [client] section options into config dict."""
    if not parser.has_section('client'):
        return

    for key, option in [('client_type', 'type'), ('host', 'host'),
                        ('port', 'port'), ('username', 'username'),
                        ('password', 'password')]:
        val = _get_string_option(parser, 'client', option)
        if val:
            config[key] = val


def _load_ui_section(parser: configparser.ConfigParser,
                     config: dict) -> None:
    """Load [ui] section options into config dict."""
    if not parser.has_section('ui'):
        return

    val = _get_string_option(parser, 'ui', 'view_mode')
    if val:
        config['view_mode'] = val
    val = _get_int_option(parser, 'ui', 'page_size')
    if val is not None:
        config['page_size'] = val
    val = _get_int_option(parser, 'ui', 'refresh_interval')
    if val is not None:
        config['refresh_interval'] = val
    val = _get_int_option(parser, 'ui', 'limit_torrents')
    if val is not None:
        config['limit_torrents'] = val


def _load_debug_section(parser: configparser.ConfigParser,
                        config: dict) -> None:
    """Load [debug] section options into config dict."""
    if not parser.has_section('debug'):
        return

    val = _get_bool_option(parser, 'debug', 'logs')
    if val is not None:
        config['logs'] = val
    val = _get_int_option(parser, 'debug', 'test_mode')
    if val is not None:
        config['test_mode'] = val


def load_config() -> dict:
    """
    Load configuration from INI file.

    Returns dictionary with config values. Returns empty dict if file
    doesn't exist or on parsing errors.
    """
    config_path = get_config_path()

    if not config_path.exists():
        return {}

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path)
    except configparser.Error as e:
        print(f"Warning: Failed to parse config file "
              f"{config_path}: {e}", file=sys.stderr)
        print("Continuing with default values...", file=sys.stderr)
        return {}

    config = {}
    _load_client_section(parser, config)
    _load_ui_section(parser, config)
    _load_debug_section(parser, config)

    return config


def create_default_config(path: Path) -> None:
    """
    Create a default configuration file with comments.

    Args:
        path: Path where the config file should be created
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    config_content = """\
# Tewi Configuration File
# This file uses INI format. Empty values use defaults.

[client]
# BitTorrent client type: transmission or qbittorrent
type =

# Daemon connection settings
host =
port =

# Authentication (leave empty if not required)
username =
password =

[ui]
# View mode for torrent list: card, compact, or oneline
view_mode =

# Number of torrents displayed per page
page_size =

# Refresh interval in seconds for loading data from daemon
refresh_interval =

# Maximum number of torrents to display
limit_torrents =

[debug]
# Enable verbose logs: boolean (saved to tewi_<timestamp>.log file)
logs =
"""

    try:
        path.write_text(config_content)
    except OSError as e:
        print(f"Error: Failed to create config file {path}: {e}",
              file=sys.stderr)
        sys.exit(1)


def merge_config_with_args(config: dict, args: Namespace) -> None:
    """
    Merge config file values with CLI arguments.

    CLI arguments take priority over config file values.
    Modifies args in place by setting defaults from config.

    Args:
        config: Dictionary of config values from load_config()
        args: Parsed command-line arguments from argparse
    """
    # Default values from argparse - used to detect if CLI arg was provided
    defaults = {
        'client_type': 'transmission',
        'view_mode': 'card',
        'refresh_interval': 5,
        'limit_torrents': None,
        'page_size': 30,
        'host': 'localhost',
        'port': '9091',
        'username': None,
        'password': None,
        'logs': False,
        'test_mode': None,
    }

    # Apply config values only for args that are at default values
    for key, default_val in defaults.items():
        if key in config and getattr(args, key) == default_val:
            setattr(args, key, config[key])
