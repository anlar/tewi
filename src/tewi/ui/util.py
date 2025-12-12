"""UI utility functions."""

import math
from datetime import datetime
from functools import cache
from typing import Any

from ..torrent.models import TorrentFile, TorrentFilePriority
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


# Functions from util/data.py


@log_time
def get_file_list(files: list[TorrentFile]) -> list[dict[str, Any]]:
    """Convert file list to flattened tree structure with display formatting."""
    node = create_file_tree(files)

    items_list: list[dict[str, Any]] = []

    def flatten_tree(
        node: dict[str, Any],
        prefix: str = "",
        is_last: bool = True,
        depth: int = 0,
        current_path: str = "",
    ) -> None:
        """Recursively flatten tree structure into list with tree symbols."""
        items = [(k, v) for k, v in node.items() if k != "__is_file__"]
        # Sort items by name (case-insensitive)
        items.sort(key=lambda x: x[0].lower())

        for i, (name, subtree) in enumerate(items):
            is_last_item = i == len(items) - 1

            # Choose the appropriate tree characters
            if prefix == "":
                current_prefix = ""
                symbol = ""  # No prefix for first level files
            else:
                symbol = "├─ " if not is_last_item else "└─ "
                current_prefix = prefix

            display_name = f"{current_prefix}{symbol}{name}"

            # Build the path for this item
            item_path = f"{current_path}{name}" if current_path else name

            if subtree.get("__is_file__", False):
                f = subtree["file"]
                completion = (f.completed / f.size) * 100
                items_list.append(
                    {
                        "is_file": True,
                        "display_name": display_name,
                        "id": f.id,
                        "size": print_size(f.size),
                        "done": f"{completion:.0f}%",
                        "priority": print_priority(f.priority),
                        # Store raw priority for styling
                        "file_priority": f.priority,
                        "depth": depth,  # Track tree depth
                        "folder_path": None,  # Files don't have folder_path
                    }
                )
            else:
                items_list.append(
                    {
                        "is_file": False,
                        "display_name": display_name,
                        "id": None,
                        "size": None,
                        "done": None,
                        "priority": None,
                        "file_priority": None,
                        "depth": depth,  # Track tree depth
                        # Store folder path for child detection
                        "folder_path": item_path,
                    }
                )

                extension = "│  " if not is_last_item else "  "
                new_prefix = current_prefix + extension
                # Pass folder path with trailing slash for next level
                next_path = f"{item_path}/"
                flatten_tree(
                    subtree, new_prefix, is_last_item, depth + 1, next_path
                )

    flatten_tree(node)

    return items_list


@log_time
def create_file_tree(files: list[TorrentFile]) -> dict[str, Any]:
    """Build hierarchical tree structure from flat list of files."""
    tree: dict[str, Any] = {}

    for file in files:
        parts = file.name.split("/")
        current = tree

        # Navigate/create the path in the tree
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {}

            # If this is the last part (filename), mark it as a file
            if i == len(parts) - 1:
                current[part]["__is_file__"] = True
                current[part]["file"] = file

            current = current[part]

    return tree


@log_time
@cache
def print_priority(priority: TorrentFilePriority) -> str:
    """Convert file priority to Rich markup string with visual indicator."""
    match priority:
        case TorrentFilePriority.NOT_DOWNLOADING:
            return "[dim]-[/]"
        case TorrentFilePriority.LOW:
            return "[dim yellow]↓[/]"
        case TorrentFilePriority.MEDIUM:
            return "→"
        case TorrentFilePriority.HIGH:
            return "[bold red]↑[/]"
