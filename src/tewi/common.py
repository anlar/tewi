from typing import NamedTuple


class FilterOption(NamedTuple):
    id: str
    name: str
    key: str
    display_name: str
    filter_func: None


filter_options = [
        FilterOption('all', 'All', 'a', '[u]A[/]ll',
                     lambda t: True),
        FilterOption('active', 'Active', 'c', 'A[u]c[/]tive',
                     lambda t: t.rate_download > 0 or t.rate_upload > 0),
        FilterOption('downloading', 'Downloading', 'd', '[u]D[/]ownloading',
                     lambda t: t.status == 'downloading'),
        FilterOption('seeding', 'Seeding', 's', '[u]S[/]eeding',
                     lambda t: t.status == 'seeding'),
        FilterOption('paused', 'Paused', 'p', '[u]P[/]aused',
                     lambda t: t.status == 'stopped'),
        FilterOption('finished', 'Finished', 'f', '[u]F[/]inished',
                     lambda t: t.percent_done >= 1.0),
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
