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

import math

from functools import cache
from datetime import datetime


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

    round(r_num, 2)

    r_size = f"{r_num:.2f}".rstrip("0").rstrip(".")

    return f"{r_size} {r_unit}{suffix}"


@cache
def print_speed(num: int, print_secs: bool = False, suffix: str = "B", speed_bytes: int = 1000) -> str:
    """Format a number of bytes per second as a human-readable speed string."""
    r_unit = None
    r_num = None

    for i in (("", 0), ("K", 0), ("M", 2), ("G", 2), ("T", 2), ("P", 2), ("E", 2), ("Z", 2), ("Y", 2)):

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


@cache
def print_ratio(ratio: float) -> str:
    if math.isinf(ratio):
        return "∞"
    else:
        return f"{ratio:.2f}"


@cache
def print_time(seconds, abbr: bool = False, units: int = 1) -> str:
    """Format a number of seconds as a human-readable time string."""
    intervals = (
            ('d', 'days', 86400),    # 60 * 60 * 24
            ('h', 'hours', 3600),    # 60 * 60
            ('m', 'minutes', 60),
            ('s', 'seconds', 1),
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
                    name = name.rstrip('s')
                result.append(f"{value:.0f} {name}")
    return ', '.join(result[:units])


@cache
def print_time_ago(dt: datetime) -> str:
    if dt is None:
        return ""

    # Ensure both datetimes are naive (no timezone info)
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
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
