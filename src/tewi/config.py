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
import sys
from argparse import Action, Namespace
from pathlib import Path

from platformdirs import user_config_dir


class TrackSetAction(Action):
    SET_POSTFIX = "_was_set"

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        setattr(namespace, f"{self.dest}{self.SET_POSTFIX}", True)


def get_config_dir() -> Path:
    """
    Get the configuration directory path using platformdirs.

    Returns the platform-appropriate user config directory for tewi.
    """
    return Path(user_config_dir("tewi", appauthor=False))


def get_config_path(profile: str | None = None) -> Path:
    """
    Get the configuration file path.

    Args:
        profile: Optional profile name. If provided, returns path to
                 tewi-PROFILE.conf, otherwise returns tewi.conf

    Returns:
        Path to the configuration file
    """
    config_dir = get_config_dir()
    if profile:
        return config_dir / f"tewi-{profile}.conf"
    else:
        return config_dir / "tewi.conf"


def get_available_profiles() -> list[str]:
    """
    Get list of available configuration profiles.

    Returns:
        List of profile names (without tewi- prefix and .conf suffix)
    """
    config_dir = get_config_dir()
    if not config_dir.exists():
        return []

    profiles = []
    for config_file in config_dir.glob("tewi-*.conf"):
        # Extract profile name from tewi-PROFILE.conf
        profile_name = config_file.stem.removeprefix("tewi-")
        profiles.append(profile_name)

    return sorted(profiles)


def _get_string_option(
    parser: configparser.ConfigParser, section: str, option: str
) -> str | None:
    """Get string option, returning None if empty or missing."""
    if parser.has_option(section, option):
        val = parser.get(section, option)
        # Return None if value is empty or contains only whitespace
        return val.strip() if val and val.strip() else None
    return None


def _get_list_option(
    parser: configparser.ConfigParser, section: str, option: str
) -> list[str] | None:
    """Get list option from comma-separated string, returning None if empty.

    Args:
        parser: ConfigParser instance
        section: Section name
        option: Option name

    Returns:
        List of stripped string values, or None if empty or missing
    """
    val = _get_string_option(parser, section, option)
    if val is None:
        return None
    # Split by comma and strip whitespace from each item
    items = [item.strip() for item in val.split(",") if item.strip()]
    return items if items else None


def _get_int_option(
    parser: configparser.ConfigParser, section: str, option: str
) -> int | None:
    """Get int option, returning None if empty, missing, or invalid."""
    val = _get_string_option(parser, section, option)
    if val is not None:
        try:
            return int(val)
        except ValueError as e:
            print(
                f"Warning: Invalid {option} value in config: {e}",
                file=sys.stderr,
            )
    return None


def _get_bool_option(
    parser: configparser.ConfigParser, section: str, option: str
) -> bool | None:
    """Get bool option, returning None if missing or invalid."""
    if parser.has_option(section, option):
        value = parser.get(section, option)
        # Return None if value is empty or contains only whitespace
        if not value or not value.strip():
            return None
        try:
            return parser.getboolean(section, option)
        except ValueError as e:
            print(
                f"Warning: Invalid {option} value in config: {e}",
                file=sys.stderr,
            )
    return None


def _load_client_section(
    parser: configparser.ConfigParser, config: dict
) -> None:
    """Load [client] section options into config dict."""
    if not parser.has_section("client"):
        return

    for key, option in [
        ("client_type", "type"),
        ("host", "host"),
        ("port", "port"),
        ("path", "path"),
        ("username", "username"),
        ("password", "password"),
    ]:
        val = _get_string_option(parser, "client", option)
        if val:
            config[key] = val


def _load_ui_section(parser: configparser.ConfigParser, config: dict) -> None:
    """Load [ui] section options into config dict."""
    if not parser.has_section("ui"):
        return

    val = _get_string_option(parser, "ui", "view_mode")
    if val:
        config["view_mode"] = val
    val = _get_int_option(parser, "ui", "page_size")
    if val is not None:
        config["page_size"] = val
    val = _get_int_option(parser, "ui", "refresh_interval")
    if val is not None:
        config["refresh_interval"] = val
    val = _get_int_option(parser, "ui", "limit_torrents")
    if val is not None:
        config["limit_torrents"] = val
    val = _get_string_option(parser, "ui", "filter")
    if val:
        config["filter"] = val
    val = _get_int_option(parser, "ui", "badge_max_count")
    if val is not None:
        config["badge_max_count"] = val
    val = _get_int_option(parser, "ui", "badge_max_length")
    if val is not None:
        config["badge_max_length"] = val


def _load_debug_section(
    parser: configparser.ConfigParser, config: dict
) -> None:
    """Load [debug] section options into config dict."""
    if not parser.has_section("debug"):
        return

    val = _get_string_option(parser, "debug", "log_level")
    if val:
        config["log_level"] = val
    val = _get_int_option(parser, "debug", "test_mode")
    if val is not None:
        config["test_mode"] = val


def _load_search_section(
    parser: configparser.ConfigParser, config: dict
) -> None:
    """Load [search] section options into config dict."""
    if not parser.has_section("search"):
        return

    val = _get_string_option(parser, "search", "jackett_url")
    if val:
        config["jackett_url"] = val
    val = _get_string_option(parser, "search", "jackett_api_key")
    if val:
        config["jackett_api_key"] = val
    val = _get_bool_option(parser, "search", "jackett_multi")
    if val is not None:
        config["jackett_multi"] = val
    val = _get_string_option(parser, "search", "prowlarr_url")
    if val:
        config["prowlarr_url"] = val
    val = _get_string_option(parser, "search", "prowlarr_api_key")
    if val:
        config["prowlarr_api_key"] = val
    val = _get_bool_option(parser, "search", "prowlarr_multi")
    if val is not None:
        config["prowlarr_multi"] = val
    val = _get_string_option(parser, "search", "bitmagnet_url")
    if val:
        config["bitmagnet_url"] = val
    val = _get_list_option(parser, "search", "providers")
    if val:
        config["search_providers"] = val


def _load_config_file(config_path: Path, config: dict) -> None:
    """
    Load configuration from a single INI file and merge into config dict.

    Args:
        config_path: Path to the config file
        config: Dictionary to merge config values into
    """
    if not config_path.exists():
        return

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path)
    except configparser.Error as e:
        print(
            f"Warning: Failed to parse config file {config_path}: {e}",
            file=sys.stderr,
        )
        print("Continuing with default values...", file=sys.stderr)
        return

    _load_client_section(parser, config)
    _load_ui_section(parser, config)
    _load_debug_section(parser, config)
    _load_search_section(parser, config)


def load_config(profile: str | None = None) -> dict:
    """
    Load configuration from INI file(s).

    If profile is specified, loads base config (tewi.conf) first, then
    overlays profile config (tewi-PROFILE.conf) on top.

    Args:
        profile: Optional profile name. If provided, also loads
                 tewi-PROFILE.conf after tewi.conf

    Returns:
        Dictionary with config values. Returns empty dict if files
        don't exist or on parsing errors.
    """
    config = {}

    # Load base config first
    base_config_path = get_config_path()
    _load_config_file(base_config_path, config)

    # If profile is specified, load and overlay profile config
    if profile:
        profile_config_path = get_config_path(profile)
        if not profile_config_path.exists():
            print(
                f"Error: Profile config not found: {profile_config_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        _load_config_file(profile_config_path, config)

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
# BitTorrent client type: transmission, qbittorrent, or deluge
type =

# Daemon connection settings
host =
port =

# Authentication (leave empty if not required)
username =
password =

# RPC path for Transmission or base JSON path for Deluge
# (leave empty for defaults)
path =

[ui]
# View mode for torrent list: card, compact, or oneline
view_mode =

# Number of torrents displayed per page
page_size =

# Filter torrents by status: all, active, downloading, seeding, paused, finished
filter =

# Maximum number of badges to display (-1: unlimited, 0: none, 1+: count)
badge_max_count =

# Maximum length of badge text (0: unlimited, 1+: truncate with …)
badge_max_length =

# Refresh interval in seconds for loading data from daemon
refresh_interval =

[search]
# Jackett server configuration for torrent search
# URL of your Jackett instance (default: http://localhost:9117)
jackett_url =

# API key for Jackett authentication
jackett_api_key =

# Multi-indexer mode for Jackett (default: false)
# When false: Shows single "Jackett" entry in search dialog, searches all
#             indexers via /all endpoint. Sub-indexers still appear in results.
# When true: Loads all Jackett indexers individually in search dialog
jackett_multi =

# Prowlarr server configuration for torrent search
# URL of your Prowlarr instance (default: http://localhost:9696)
prowlarr_url =

# API key for Prowlarr authentication
prowlarr_api_key =

# Multi-indexer mode for Prowlarr (default: false)
# When false: Shows single "Prowlarr" entry in search dialog, searches all
#             indexers. Sub-indexers still appear in results.
# When true: Loads all Prowlarr indexers individually in search dialog
prowlarr_multi =

# Bitmagnet server configuration for torrent search
# URL of your Bitmagnet instance (default: http://localhost:3333)
bitmagnet_url =

# Comma-separated list of enabled search providers
# Leave empty to enable default providers
# Order matters: providers listed first take priority when deduplicating
# results and appear first in the search dialog
providers =

[debug]
# Log level: debug, info, warning, error, critical
log_level =

"""

    try:
        path.write_text(config_content)
    except OSError as e:
        print(
            f"Error: Failed to create config file {path}: {e}", file=sys.stderr
        )
        sys.exit(1)


def merge_config_with_args(config: dict, args: Namespace) -> None:
    """
    Merge config file values with CLI arguments.

    CLI arguments take priority over config file values.
    Modifies args in place.

    Args:
        config: Dictionary of config values from load_config()
        args: Parsed command-line arguments from argparse
    """

    for key, value in config.items():
        if not hasattr(args, f"{key}{TrackSetAction.SET_POSTFIX}"):
            setattr(args, key, value)
