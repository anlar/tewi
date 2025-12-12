"""Utility functions for torrent operations."""

import math
from dataclasses import replace

from .models import Torrent


def torrents_test(torrents: list[Torrent], target_count: int) -> list[Torrent]:
    """Get test torrent list (for performance testing).

    Args:
        torrents: List of source torrents to duplicate
        target_count: Target number of test torrents to generate (approximate)

    Returns:
        List of duplicated Torrent objects (~target_count items)
    """
    if not torrents:
        return []

    # Calculate multiplier to achieve approximately target_count torrents
    multiplier = max(1, math.ceil(target_count / len(torrents)))

    result = []
    idx = 1

    for i in range(multiplier):
        for t in torrents:
            t_copy = replace(t, id=idx, name=t.name + "-" + str(idx))
            result.append(t_copy)
            idx = idx + 1

    return result


def count_torrents_by_status(torrents: list[Torrent]) -> dict[str, int]:
    """Count torrents by status and calculate sizes.

    This is a helper function for computing torrent statistics.

    Args:
        torrents: List of torrents to count

    Returns:
        Dictionary with keys:
            - count: Total number of torrents
            - down: Number of downloading torrents
            - seed: Number of seeding torrents
            - check: Number of checking torrents
            - stop: Number of stopped torrents
            - complete_size: Total completed bytes
            - total_size: Total size when done in bytes
    """
    count = len(torrents)
    down = 0
    seed = 0
    check = 0
    complete_size = 0
    total_size = 0

    for t in torrents:
        total_size += t.size_when_done
        complete_size += t.size_when_done - t.left_until_done

        if t.status == "downloading":
            down += 1
        elif t.status == "seeding":
            seed += 1
        elif t.status == "checking":
            check += 1

    stop = count - down - seed - check

    return {
        "count": count,
        "down": down,
        "seed": seed,
        "check": check,
        "stop": stop,
        "complete_size": complete_size,
        "total_size": total_size,
    }
