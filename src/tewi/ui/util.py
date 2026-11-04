"""UI utility functions."""

import math
import os
import platform
import subprocess
from datetime import datetime
from functools import lru_cache

from rich.text import Text
from textual.color import Color

from ..util.log import get_logger, log_time
from ..util.misc import is_http_url

logger = get_logger()


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
    """Open file or URL using platform-specific default application.

    Args:
        path: File path or URL to open

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


def open_url(url: str) -> bool:
    """Open HTTP(S) URL using platform-specific default application.

    Use it instead of `open` for URLs from remote sources (e.g. search
    providers): other values (file paths, file:// or custom scheme URLs,
    UNC paths on Windows) are rejected, as default application could
    open local files or leak credentials for them.

    Args:
        url: URL to open

    Returns:
        False if URL was rejected

    Raises:
        Exception: If opening fails on the current platform
    """
    if not is_http_url(url):
        logger.warning(f"Rejected opening non-HTTP(S) URL: {url!r}")
        return False
    open(url.strip())
    return True


# Functions from util/print.py

FORMAT_CACHE_SIZE = 20000


@log_time
@lru_cache(maxsize=FORMAT_CACHE_SIZE)
def print_size(
    num: int,
    suffix: str = "B",
    size_bytes: int = 1000,
    ndigits: int = 2,
    int_width: int = 0,
    unit_width: int = 0,
) -> str:
    """Format a number of bytes as a human-readable size string."""
    r_unit = None
    r_num = None

    for unit in ("", "k", "M", "G", "T", "P", "E", "Z", "Y"):
        if abs(num) < size_bytes:
            r_unit = unit
            r_num = num
            break
        num /= size_bytes

    width = int_width + (ndigits + 1 if ndigits and int_width else 0)
    r_size = f"{r_num:.{ndigits}f}"
    if "." in r_size:
        r_size = r_size.rstrip("0").rstrip(".")
    r_size = r_size.rjust(width)

    return f"{r_size} {r_unit:{' '}>{unit_width}}{suffix}"


@log_time
@lru_cache(maxsize=FORMAT_CACHE_SIZE)
def print_speed(
    num: int,
    print_secs: bool = False,
    suffix: str = "B",
    speed_bytes: int = 1000,
    dash_for_zero: bool = False,
) -> str:
    """Format a number of bytes per second as a human-readable speed string.

    Args:
        num: Speed in bytes per second
        print_secs: If True, append "/s" suffix
        suffix: Unit suffix (default: "B")
        speed_bytes: Divisor for unit conversion (default: 1000)
        dash_for_zero: If True, return "-" for zero values (default: False)

    Returns:
        Formatted speed string or "-" if num is 0 and dash_for_zero is True
    """
    if dash_for_zero and not num:
        return "-"

    r_unit = None
    r_num = None

    for i in (
        ("", 0),
        ("K", 0),
        ("M", 2),
        ("G", 2),
        ("T", 2),
        ("P", 2),
        ("E", 2),
        ("Z", 2),
        ("Y", 2),
    ):
        if abs(num) < speed_bytes:
            r_unit = i[0]
            r_num = round(num, i[1])
            break
        num /= speed_bytes

    r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

    if print_secs:
        return f"{r_size} {r_unit}{suffix}/s"
    else:
        return f"{r_size} {r_unit}{suffix}"


@log_time
@lru_cache(maxsize=FORMAT_CACHE_SIZE)
def print_ratio(ratio: float, ndigits: int = 2) -> str:
    if math.isinf(ratio):
        return "∞"
    else:
        return f"{ratio:.{ndigits}f}"


@log_time
@lru_cache(maxsize=FORMAT_CACHE_SIZE)
def print_time(seconds, abbr: bool = False, units: int = 1) -> str:
    """Format a number of seconds as a human-readable time string."""
    intervals = (
        ("d", "days", 86400),  # 60 * 60 * 24
        ("h", "hours", 3600),  # 60 * 60
        ("m", "minutes", 60),
        ("s", "seconds", 1),
    )
    result = []

    for key, name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if abbr is True:
                result.append(f"{value:.0f}{key}")
            else:
                if value == 1:
                    name = name.rstrip("s")
                result.append(f"{value:.0f} {name}")
    return ", ".join(result[:units])


@log_time
def print_time_ago(dt: datetime) -> str:
    if dt is None:
        return ""

    # Ensure both datetimes are naive (no timezone info)
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        # Convert to naive datetime
        dt = dt.replace(tzinfo=None)

    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:  # 7 days
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif seconds < 2592000:  # 30 days
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    elif seconds < 31536000:  # 365 days
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months > 1 else ''} ago"
    else:
        years = int(seconds / 31536000)
        return f"{years} year{'s' if years > 1 else ''} ago"


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

    Args:
        value: Value to show (None is shown as empty string)
        style: Optional Rich style for the whole text
        **kwargs: Extra arguments for Text (e.g. justify)
    """
    return Text("" if value is None else str(value), style=style, **kwargs)


def source_text(name: str, source: str, short: bool = False) -> Text:
    """Build name with dimmed aggregator source as Text (never markup).

    Args:
        name: Indexer or provider name (from remote source)
        source: Aggregator name or tag (e.g. "Jackett", "J"), may be empty
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
