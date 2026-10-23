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

"""Custom color themes defined in [theme.NAME] config sections."""

import configparser
import dataclasses
import re

from textual.color import Color, ColorParseError
from textual.theme import BUILTIN_THEMES, Theme

THEME_SECTION_PREFIX = "theme."

# Theme colors, in the order of textual.theme.Theme fields
THEME_COLOR_KEYS = (
    "primary",
    "secondary",
    "warning",
    "error",
    "success",
    "accent",
    "foreground",
    "background",
    "surface",
    "panel",
    "boost",
)

THEME_OPTION_KEYS = ("base", "dark", *THEME_COLOR_KEYS)

_HEX_COLOR_PATTERN = re.compile(
    r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"
)
_NAMED_COLOR_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


class ThemeConfigError(ValueError):
    """Raised when custom theme configuration is invalid."""


def parse_color(value: str) -> str:
    """Validate theme color value.

    Only Textual color names (e.g. "crimson", "ansi_bright_blue") and hex
    codes (#RGB, #RGBA, #RRGGBB, #RRGGBBAA) are accepted.

    Args:
        value: Color value from config

    Returns:
        Validated color value

    Raises:
        ThemeConfigError: If value is not a valid color name or hex code
    """
    if not (
        _HEX_COLOR_PATTERN.fullmatch(value)
        or _NAMED_COLOR_PATTERN.fullmatch(value)
    ):
        raise ThemeConfigError(
            f"invalid color '{value}' (use color name or #RRGGBB code)"
        )
    try:
        Color.parse(value)
    except ColorParseError:
        raise ThemeConfigError(f"unknown color '{value}'") from None
    return value


def _parse_dark(value: str) -> bool:
    """Parse dark option value as boolean."""
    states = configparser.ConfigParser.BOOLEAN_STATES
    if value.lower() not in states:
        raise ThemeConfigError(
            f"invalid dark value '{value}' (use true or false)"
        )
    return states[value.lower()]


def validate_theme_options(name: str, options: dict[str, str]) -> None:
    """Validate options of single [theme.NAME] section.

    Args:
        name: Theme name
        options: Section options (key to value)

    Raises:
        ThemeConfigError: If theme name, option key or value is invalid
    """
    if not name:
        raise ThemeConfigError("theme name must not be empty")
    for key, value in options.items():
        if key not in THEME_OPTION_KEYS:
            raise ThemeConfigError(
                f"[{THEME_SECTION_PREFIX}{name}]: unknown option '{key}' "
                f"(available: {', '.join(THEME_OPTION_KEYS)})"
            )
        try:
            if key == "dark":
                _parse_dark(value)
            elif key in THEME_COLOR_KEYS:
                parse_color(value)
        except ThemeConfigError as e:
            raise ThemeConfigError(
                f"[{THEME_SECTION_PREFIX}{name}]: {key}: {e}"
            ) from None
    if "base" in options and name in BUILTIN_THEMES:
        raise ThemeConfigError(
            f"[{THEME_SECTION_PREFIX}{name}]: base can't be used when "
            "overriding built-in theme"
        )


def _build_theme(
    name: str, options: dict[str, str], available: dict[str, Theme]
) -> Theme:
    """Build theme from validated section options.

    Built-in theme with the same name, or theme from "base" option, is used
    as base: options override its colors, other values are kept.
    """
    section = f"[{THEME_SECTION_PREFIX}{name}]"
    colors = {k: options[k] for k in THEME_COLOR_KEYS if k in options}
    if "dark" in options:
        colors["dark"] = _parse_dark(options["dark"])

    base_name = name if name in BUILTIN_THEMES else options.get("base")
    if base_name is not None:
        base = available.get(base_name)
        if base is None:
            raise ThemeConfigError(
                f"{section}: unknown base theme '{base_name}' (use built-in "
                "theme or custom theme defined before this one)"
            )
        return dataclasses.replace(base, name=name, **colors)

    if "primary" not in colors:
        raise ThemeConfigError(
            f"{section}: primary color is required when base is not set"
        )
    return Theme(name=name, **colors)


def build_custom_themes(sections: dict[str, dict[str, str]]) -> list[Theme]:
    """Build custom themes from [theme.NAME] config sections.

    Args:
        sections: Theme name to its options, in config order

    Returns:
        List of themes, in config order

    Raises:
        ThemeConfigError: If any theme is invalid
    """
    available = dict(BUILTIN_THEMES)
    themes = []
    for name, options in sections.items():
        validate_theme_options(name, options)
        theme = _build_theme(name, options, available)
        available[name] = theme
        themes.append(theme)
    return themes
