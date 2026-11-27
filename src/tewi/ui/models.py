# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import Counter
from collections.abc import Callable
from enum import Enum
from typing import Any, NamedTuple

from ..torrent.base import ClientCapability
from ..torrent.models import Torrent


class PageState(NamedTuple):
    current: int
    total: int


class MarkState(NamedTuple):
    """Count of marked torrents in torrent list."""

    listed: int
    """Marked torrents shown by current filter (used by actions)."""

    hidden: int
    """Marked torrents hidden by current filter (kept, but not used)."""


class SortOrder(NamedTuple):
    id: str
    name: str
    key_asc: str
    key_desc: str
    sort_func: Callable[[Torrent], Any]


sort_orders = [
    SortOrder("age", "Age", "a", "A", lambda t: t.added_date),
    SortOrder("name", "Name", "n", "N", lambda t: t.name.lower()),
    SortOrder("size", "Size", "z", "Z", lambda t: t.size_when_done),
    SortOrder("status", "Status", "t", "T", lambda t: t.status),
    SortOrder("priority", "Priority", "i", "I", lambda t: t.priority),
    SortOrder(
        "queue_order",
        "Queue Order",
        "o",
        "O",
        lambda t: (
            t.queue_position if t.queue_position is not None else float("inf")
        ),
    ),
    SortOrder("ratio", "Ratio", "r", "R", lambda t: t.ratio),
    SortOrder("progress", "Progress", "p", "P", lambda t: t.percent_done),
    SortOrder("activity", "Activity", "y", "Y", lambda t: t.activity_date),
    SortOrder("uploaded", "Uploaded", "u", "U", lambda t: t.uploaded_ever),
    SortOrder("peers", "Peers", "e", "E", lambda t: t.peers_connected),
    SortOrder("seeders", "Seeders", "s", "S", lambda t: t.peers_sending_to_us),
    SortOrder(
        "leechers", "Leechers", "l", "L", lambda t: t.peers_getting_from_us
    ),
]


class SortKey(NamedTuple):
    """Single sort order with its direction."""

    order: SortOrder
    is_asc: bool


default_sort_keys = (SortKey(sort_orders[0], True),)


def sort_torrents(torrents: list, sort_keys: tuple[SortKey, ...]) -> None:
    """Sort torrents in place by multiple keys.

    First key has highest priority, following keys break ties. Relies on
    sort stability: sorts by least significant key first.

    Args:
        torrents: List of torrents to sort
        sort_keys: Sort keys ordered by priority
    """
    for key in reversed(sort_keys):
        torrents.sort(key=key.order.sort_func, reverse=not key.is_asc)


class FilterOption(NamedTuple):
    id: str
    name: str
    key: str
    display_name: str
    filter_func: Callable[[Torrent], bool]


class TagType(Enum):
    CATEGORY = "Category"
    LABEL = "Label"

    @property
    def capability(self) -> ClientCapability:
        """Client capability required to filter by this tag type."""
        return ClientCapability[self.name]

    @property
    def key(self) -> str:
        """Key to open filter by this tag type in filter dialog."""
        return self.value[0].lower()

    @property
    def display_name(self) -> str:
        """Filter dialog row with underlined key."""
        return f"[u]{self.value[0]}[/]{self.value[1:]}..."

    def names(self, torrent: Torrent) -> set[str]:
        """Get torrent category or labels.

        Args:
            torrent: Torrent to get names of

        Returns:
            Category (empty if torrent has none) or labels of torrent
        """
        if self == TagType.CATEGORY:
            return {torrent.category} if torrent.category else set()
        return set(torrent.labels)


def count_tags(
    torrents: list[Torrent], tag_type: TagType, current: str | None = None
) -> dict[str, int]:
    """Count torrents per category or label.

    Args:
        torrents: Torrents to count
        tag_type: Count categories or labels
        current: Name of current filter, included even if no torrent has
            it, so filter is shown (e.g. set in config with a typo)

    Returns:
        Torrent count per category/label name, sorted by name
    """
    counts = Counter(name for t in torrents for name in tag_type.names(t))
    if current is not None:
        counts[current] += 0
    # Exact name breaks ties of names differing only in case, so their
    # order doesn't depend on set iteration
    return dict(sorted(counts.items(), key=lambda x: (x[0].lower(), x[0])))


class FilterState(NamedTuple):
    option: FilterOption
    torrent_count: int
    name: str = ""
    tags: tuple[tuple[TagType, str], ...] = ()
    """Pairs of tag type and category/label name."""


filter_options = [
    FilterOption("all", "All", "a", "[u]A[/]ll", lambda t: True),
    FilterOption(
        "active",
        "Active",
        "t",
        "Ac[u]t[/]ive",
        lambda t: t.rate_download > 0 or t.rate_upload > 0,
    ),
    FilterOption(
        "downloading",
        "Downloading",
        "d",
        "[u]D[/]ownloading",
        lambda t: t.status == "downloading",
    ),
    FilterOption(
        "seeding",
        "Seeding",
        "s",
        "[u]S[/]eeding",
        lambda t: t.status == "seeding",
    ),
    FilterOption(
        "checking",
        "Checking",
        "h",
        "C[u]h[/]ecking",
        lambda t: t.status in ("checking", "check pending"),
    ),
    FilterOption(
        "paused", "Paused", "p", "[u]P[/]aused", lambda t: t.status == "stopped"
    ),
    FilterOption(
        "incomplete",
        "Incomplete",
        "i",
        "[u]I[/]ncomplete",
        lambda t: t.percent_done < 1.0,
    ),
    FilterOption(
        "finished",
        "Finished",
        "f",
        "[u]F[/]inished",
        lambda t: t.percent_done >= 1.0,
    ),
]


def get_filter_by_id(filter_id: str) -> FilterOption:
    """Get filter option by ID.

    Args:
        filter_id: The filter ID to search for

    Returns:
        FilterOption matching the ID

    Raises:
        ValueError: If filter_id is not found
    """
    for filter_option in filter_options:
        if filter_option.id == filter_id:
            return filter_option
    raise ValueError(f"Unknown filter ID: {filter_id}")


def parse_filter(value: str) -> tuple[FilterOption, dict[TagType, str]]:
    """Parse filter from CLI or config.

    Filter is comma-separated list of state (e.g. "seeding") and
    "category:NAME" or "label:NAME", at most one of each kind.

    Args:
        value: Filter like "seeding,label:hd"

    Returns:
        Filter by state ("all" if not set) and category/label name per tag
        type

    Raises:
        ValueError: If filter is invalid
    """
    option = None
    tags: dict[TagType, str] = {}
    tag_types = {t.value.lower(): t for t in TagType}

    for item in (x.strip() for x in value.split(",")):
        if not item:
            continue

        prefix, sep, name = item.partition(":")

        if not sep:
            # Checked before duplicates: category/label without prefix
            # (e.g. "seeding,hd") is reported as unknown, not second state
            try:
                state = get_filter_by_id(item.lower())
            except ValueError:
                states = ", ".join(f.id for f in filter_options)
                raise ValueError(
                    f"unknown filter '{item}' (use state: {states}; "
                    "or category:NAME, label:NAME)"
                ) from None
            if option is not None:
                raise ValueError(f"more than one state in filter: {value}")
            option = state
            continue

        tag_type = tag_types.get(prefix.strip().lower())
        name = name.strip()

        if not tag_type:
            raise ValueError(
                f"unknown filter '{item}' (use category:NAME or label:NAME)"
            )
        if not name:
            raise ValueError(f"empty name in filter '{item}'")
        if tag_type in tags:
            raise ValueError(
                f"more than one {tag_type.value.lower()} in filter: {value}"
            )

        tags[tag_type] = name

    if option is None:
        option = get_filter_by_id("all")

    return option, tags


def filter_torrents(
    torrents: list[Torrent],
    option: FilterOption,
    name: str,
    tags: dict[TagType, str],
) -> list[Torrent]:
    """Filter torrents by state, name and category/label.

    Args:
        torrents: Torrents to filter
        option: Filter by state
        name: Part of torrent name (case-insensitive), empty to skip
        tags: Category/label name per tag type (exact match)

    Returns:
        Torrents matching all filters, in original order
    """
    name = name.lower()

    return [
        t
        for t in torrents
        if option.filter_func(t)
        and name in t.name.lower()
        and all(n in tag_type.names(t) for tag_type, n in tags.items())
    ]
