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
from textual.theme import BUILTIN_THEMES

from src.tewi.theme import (
    ThemeConfigError,
    build_custom_themes,
    parse_color,
    validate_theme_options,
)


class TestParseColor:
    """Test cases for parse_color function."""

    @pytest.mark.parametrize(
        "value",
        [
            "red",
            "darkslateblue",
            "ansi_bright_blue",
            "#abc",
            "#abcd",
            "#AABBCC",
            "#aabbccdd",
        ],
    )
    def test_valid_colors(self, value):
        """Test that color names and hex codes are accepted."""
        assert parse_color(value) == value

    @pytest.mark.parametrize(
        "value",
        [
            "rgb(1, 2, 3)",
            "hsl(0, 50%, 50%)",
            "notacolor",
            "Red",
            "#ab",
            "#abcde",
            "#gggggg",
            "red 50%",
        ],
    )
    def test_invalid_colors(self, value):
        """Test that other color formats are rejected."""
        with pytest.raises(ThemeConfigError):
            parse_color(value)


class TestValidateThemeOptions:
    """Test cases for validate_theme_options function."""

    def test_valid_options(self):
        """Test that all supported options are accepted."""
        validate_theme_options(
            "mine",
            {
                "base": "nord",
                "dark": "false",
                "primary": "red",
                "secondary": "#00ff00",
                "accent": "blue",
                "warning": "orange",
                "error": "crimson",
                "success": "green",
                "foreground": "#eeeeee",
                "background": "#111111",
                "surface": "#222222",
                "panel": "#333333",
                "boost": "#ffffff10",
            },
        )

    def test_empty_name(self):
        """Test that empty theme name is rejected."""
        with pytest.raises(ThemeConfigError, match="name"):
            validate_theme_options("", {"primary": "red"})

    def test_unknown_option(self):
        """Test that non-color options (e.g. CSS variables) are rejected."""
        with pytest.raises(ThemeConfigError, match="block-cursor"):
            validate_theme_options("mine", {"block-cursor": "red"})

    def test_invalid_dark(self):
        """Test that invalid dark value is rejected."""
        with pytest.raises(ThemeConfigError, match="dark"):
            validate_theme_options("mine", {"dark": "maybe"})

    def test_base_on_builtin_override(self):
        """Test that base can't be set when overriding built-in theme."""
        with pytest.raises(ThemeConfigError, match="base"):
            validate_theme_options("nord", {"base": "gruvbox"})


class TestBuildCustomThemes:
    """Test cases for build_custom_themes function."""

    def test_empty(self):
        """Test that no sections produce no themes."""
        assert build_custom_themes({}) == []

    def test_new_theme(self):
        """Test theme without base."""
        (theme,) = build_custom_themes(
            {"mine": {"primary": "#ff0000", "dark": "no"}}
        )

        assert theme.name == "mine"
        assert theme.primary == "#ff0000"
        assert theme.dark is False

    def test_new_theme_requires_primary(self):
        """Test that theme without base requires primary color."""
        with pytest.raises(ThemeConfigError, match="primary"):
            build_custom_themes({"mine": {"accent": "red"}})

    def test_override_builtin(self):
        """Test that built-in theme colors are overridden."""
        nord = BUILTIN_THEMES["nord"]

        (theme,) = build_custom_themes({"nord": {"background": "black"}})

        assert theme.name == "nord"
        assert theme.background == "black"
        assert theme.primary == nord.primary
        assert theme.variables == nord.variables
        # Built-in theme itself is unchanged
        assert BUILTIN_THEMES["nord"].background != "black"

    def test_override_keeps_ansi(self):
        """Test that ANSI flag of built-in theme is kept."""
        (theme,) = build_custom_themes({"ansi-dark": {"primary": "ansi_red"}})

        assert theme.ansi is True

    def test_base_builtin(self):
        """Test theme based on built-in theme."""
        gruvbox = BUILTIN_THEMES["gruvbox"]

        (theme,) = build_custom_themes(
            {"mine": {"base": "gruvbox", "accent": "gold"}}
        )

        assert theme.name == "mine"
        assert theme.accent == "gold"
        assert theme.primary == gruvbox.primary
        assert theme.dark == gruvbox.dark

    def test_base_custom_defined_before(self):
        """Test theme based on custom theme defined before it."""
        first, second = build_custom_themes(
            {
                "first": {"primary": "red", "dark": "false"},
                "second": {"base": "first", "accent": "blue"},
            }
        )

        assert second.primary == "red"
        assert second.accent == "blue"
        assert second.dark is False

    def test_base_custom_defined_after(self):
        """Test that base must be defined before theme using it."""
        with pytest.raises(ThemeConfigError, match="unknown base"):
            build_custom_themes(
                {
                    "second": {"base": "first"},
                    "first": {"primary": "red"},
                }
            )

    def test_unknown_base(self):
        """Test that unknown base theme is rejected."""
        with pytest.raises(ThemeConfigError, match="unknown base"):
            build_custom_themes({"mine": {"base": "nope"}})
