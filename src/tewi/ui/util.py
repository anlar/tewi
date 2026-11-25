# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""UI utility functions."""

import os
import platform
import subprocess
from functools import lru_cache

from rich.text import Text
from textual.color import Color

from ..util.format import FORMAT_CACHE_SIZE
from ..util.misc import strip_control_chars


def subtitle_keys(*key_desc_pairs: tuple[str, str]) -> str:
    """Format key bindings for border subtitle display.

    Args:
        *key_desc_pairs: Variable number of (key, description) tuples

    Returns:
        Formatted string like
        "<A> [dim]Add[/] [dim]·[/] <O> [dim]Open[/]"

    Example:
        >>> subtitle_keys(("Y", "Yes"), ("N", "No"))
        "<Y> [dim]Yes[/] [dim]·[/] <N> [dim]No[/]"
        >>> subtitle_keys(("Enter", "Search"), ("ESC", "Close"))
        "<Enter> [dim]Search[/] [dim]·[/] <ESC> [dim]Close[/]"
    """
    return " [dim]·[/] ".join(
        f"<{key}> [dim]{desc}[/]" for key, desc in key_desc_pairs
    )


def open(path: str) -> None:
    """Open local file using platform-specific default application.

    Use `App.open_url` for URLs, it accepts only HTTP(S) ones.

    Args:
        path: File path to open

    Raises:
        Exception: If opening fails on the current platform
    """
    # Platform opener is found in PATH, and path is passed as single
    # argument without shell
    system = platform.system()
    if system == "Linux":
        subprocess.Popen(  # noqa: S603
            ["xdg-open", path],  # noqa: S607
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif system == "Darwin":  # macOS
        subprocess.Popen(  # noqa: S603
            ["open", path],  # noqa: S607
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif system == "Windows":
        os.startfile(path)  # noqa: S606
    else:
        raise Exception(f"Unsupported platform: {system}")


def theme_markup_color(app, variable: str) -> str:
    """Get theme color variable as color name usable in Rich markup.

    Widgets like DataTable don't support CSS variables in markup, so colors
    are resolved from theme. Theme values may be ANSI colors (e.g.
    "ansi_green" in ANSI themes) which Rich markup doesn't accept, so they
    are converted to Rich color names (e.g. "color(2)").

    Args:
        app: Textual application
        variable: Theme CSS variable name without "$", e.g. "text-success"

    Returns:
        Color name, e.g. "#8ad4a1" or "color(2)"
    """
    value = app.get_css_variables()[variable]
    return Color.parse(value).rich_color.name


def plain_text(value: object, style: str = "", **kwargs) -> Text:
    """Wrap value as Text, so widgets don't parse it as markup.

    DataTable and other widgets parse str values as Rich markup, which
    lets text from remote sources (torrent and file names, peer clients,
    tracker messages, search results) inject styles, links or
    "[@click=...]" actions triggered by a mouse click. Use this for all
    such values instead of passing them as str.

    Control characters are removed too, as not all remote text comes
    from DTOs which strip them (e.g. client preferences).

    Args:
        value: Value to show (None is shown as empty string)
        style: Optional Rich style for the whole text
        **kwargs: Extra arguments for Text (e.g. justify)
    """
    text = "" if value is None else strip_control_chars(str(value))
    return Text(text, style=style, **kwargs)


def source_text(name: str, source: str | None, short: bool = False) -> Text:
    """Build name with dimmed aggregator source as Text (never markup).

    Args:
        name: Indexer or provider name (from remote source)
        source: Aggregator name or tag (e.g. "Jackett", "J"), or None
        short: Use compact format "name|J" instead of "name (J)"
    """
    text = plain_text(name)
    if source:
        suffix = f"|{source}" if short else f" ({source})"
        text.append(suffix, style="dim")
    return text


@lru_cache(maxsize=FORMAT_CACHE_SIZE)
def truncate(value: str, max_len: int) -> str:
    """Truncate value to `max_len` chars (plus ellipsis), 0 means no limit."""
    return (
        value[:max_len] + "…"
        if (max_len > 0 and len(value) > max_len)
        else value
    )
