"""UI utility functions."""

import math
from datetime import datetime
from functools import cache

from ..util.log import log_time


def subtitle_keys(*key_desc_pairs: tuple[str, str]) -> str:
    """Format key bindings for border subtitle display.

    Args:
        *key_desc_pairs: Variable number of (key, description) tuples

    Returns:
        Formatted string like "(A) Add / (O) Open / (X) Close"

    Example:
        >>> subtitle_keys(("Y", "Yes"), ("N", "No"))
        "(Y) Yes / (N) No"
        >>> subtitle_keys(("Enter", "Search"), ("ESC", "Close"))
        "(Enter) Search / (ESC) Close"
    """
    return " / ".join(f"({key}) {desc}" for key, desc in key_desc_pairs)


# Functions from util/print.py


@log_time
@cache
def print_size(num: int, suffix: str = "B", size_bytes: int = 1000) -> str:
    """Format a number of bytes as a human-readable size string."""
    r_unit = None
    r_num = None

    for unit in ("", "k", "M", "G", "T", "P", "E", "Z", "Y"):
        if abs(num) < size_bytes:
            r_unit = unit
            r_num = num
            break
        num /= size_bytes

    r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

    return f"{r_size} {r_unit}{suffix}"


@log_time
@cache
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
    if dash_for_zero and num == 0:
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
@cache
def print_ratio(ratio: float) -> str:
    if math.isinf(ratio):
        return "∞"
    else:
        return f"{ratio:.2f}"


@log_time
@cache
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
@cache
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


@cache
def escape_markup(value: str) -> str:
    return value.replace("[", r"\[")


@cache
def esc_trunk(value: str, max_len: int) -> str:
    result = (
        value[:max_len] + "…"
        if (max_len > 0 and len(value) > max_len)
        else value
    )
    return escape_markup(result)
