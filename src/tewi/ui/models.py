from typing import NamedTuple


class PageState(NamedTuple):
    current: int
    total: int


class SortOrder(NamedTuple):
    id: str
    name: str
    key_asc: str
    key_desc: str
    sort_func: None


sort_orders = [
    SortOrder("age", "Age", "a", "A", lambda t: t.added_date),
    SortOrder("name", "Name", "n", "N", lambda t: t.name.lower()),
    SortOrder("size", "Size", "z", "Z", lambda t: t.total_size),
    SortOrder("status", "Status", "t", "T", lambda t: t.status),
    SortOrder("priority", "Priority", "i", "I", lambda t: t.priority),
    SortOrder(
        "queue_order",
        "Queue Order",
        "o",
        "O",
        lambda t: t.queue_position
        if t.queue_position is not None
        else float("inf"),
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


class FilterOption(NamedTuple):
    id: str
    name: str
    key: str
    display_name: str
    filter_func: None


class FilterState(NamedTuple):
    option: FilterOption
    torrent_count: int


filter_options = [
    FilterOption("all", "All", "a", "[u]A[/]ll", lambda t: True),
    FilterOption(
        "active",
        "Active",
        "c",
        "A[u]c[/]tive",
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
        "paused", "Paused", "p", "[u]P[/]aused", lambda t: t.status == "stopped"
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
