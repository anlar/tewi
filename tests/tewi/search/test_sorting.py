from datetime import datetime

import pytest

from src.tewi.search.models import SearchResult, StandardCategories
from src.tewi.search.sorting import SEARCH_SORT_OPTIONS, sort_search_results


def result(
    title: str,
    *,
    provider: str,
    provider_short: str | None = None,
    uploaded: datetime | None,
    seeders: int | None,
    leechers: int | None,
    downloads: int | None,
    size: int | None,
    files: int | None,
    category,
) -> SearchResult:
    return SearchResult(
        title=title,
        info_hash=title,
        magnet_link=f"magnet:?xt=urn:btih:{title}",
        torrent_link=None,
        provider=provider,
        provider_id=provider,
        provider_short=provider_short or provider,
        upload_date=uploaded,
        seeders=seeders,
        leechers=leechers,
        downloads=downloads,
        size=size,
        files_count=files,
        categories=[category] if category else None,
    )


RESULTS = [
    result(
        "Beta",
        provider="Zoo",
        uploaded=datetime(2026, 1, 2),
        seeders=10,
        leechers=2,
        downloads=100,
        size=10,
        files=1,
        category=StandardCategories.MOVIES,
    ),
    result(
        "alpha",
        provider="alpha",
        uploaded=datetime(2026, 1, 1),
        seeders=1,
        leechers=9,
        downloads=5,
        size=20,
        files=3,
        category=StandardCategories.TV,
    ),
    result(
        "charlie",
        provider="middle",
        uploaded=datetime(2026, 1, 3),
        seeders=5,
        leechers=4,
        downloads=50,
        size=15,
        files=2,
        category=StandardCategories.AUDIO,
    ),
]


@pytest.mark.parametrize(
    ("key", "ascending_titles"),
    [
        ("source", ["alpha", "charlie", "Beta"]),
        ("uploaded", ["alpha", "Beta", "charlie"]),
        ("seeders", ["alpha", "charlie", "Beta"]),
        ("leechers", ["Beta", "charlie", "alpha"]),
        ("downloads", ["alpha", "charlie", "Beta"]),
        ("size", ["Beta", "charlie", "alpha"]),
        ("files", ["Beta", "charlie", "alpha"]),
        ("category", ["charlie", "Beta", "alpha"]),
        ("name", ["alpha", "Beta", "charlie"]),
    ],
)
def test_every_column_sorts_both_directions(key, ascending_titles):
    assert [r.title for r in sort_search_results(RESULTS, key, True)] == (
        ascending_titles
    )
    assert [r.title for r in sort_search_results(RESULTS, key, False)] == (
        ascending_titles[::-1]
    )


@pytest.mark.parametrize(
    "key",
    [
        "uploaded",
        "seeders",
        "leechers",
        "downloads",
        "size",
        "files",
        "category",
    ],
)
def test_missing_values_stay_last_in_both_directions(key):
    missing = result(
        "missing",
        provider="missing",
        uploaded=None,
        seeders=None,
        leechers=None,
        downloads=None,
        size=None,
        files=None,
        category=None,
    )
    for ascending in (True, False):
        sorted_results = sort_search_results(
            [missing, *RESULTS], key, ascending
        )
        assert sorted_results[-1] is missing


def test_zero_is_a_value_and_ties_keep_input_order():
    zero = result(
        "zero",
        provider="zero",
        uploaded=None,
        seeders=0,
        leechers=None,
        downloads=None,
        size=None,
        files=None,
        category=None,
    )
    missing = result(
        "missing",
        provider="missing",
        uploaded=None,
        seeders=None,
        leechers=None,
        downloads=None,
        size=None,
        files=None,
        category=None,
    )
    assert sort_search_results([missing, zero], "seeders", False) == [
        zero,
        missing,
    ]
    tie = result(
        "tie",
        provider="tie",
        uploaded=None,
        seeders=RESULTS[0].seeders,
        leechers=None,
        downloads=None,
        size=None,
        files=None,
        category=None,
    )
    assert sort_search_results([RESULTS[0], tie], "seeders", True) == [
        RESULTS[0],
        tie,
    ]


def test_sort_shortcuts_are_unique_and_cover_every_column():
    assert len({option.key for option in SEARCH_SORT_OPTIONS}) == 9
    assert len({option.hotkey for option in SEARCH_SORT_OPTIONS}) == 9


def test_compact_source_sort_uses_displayed_short_name():
    first = result(
        "first",
        provider="A provider",
        provider_short="Z",
        uploaded=None,
        seeders=None,
        leechers=None,
        downloads=None,
        size=None,
        files=None,
        category=None,
    )
    second = result(
        "second",
        provider="Z provider",
        provider_short="A",
        uploaded=None,
        seeders=None,
        leechers=None,
        downloads=None,
        size=None,
        files=None,
        category=None,
    )
    assert sort_search_results([first, second], "source", True) == [
        first,
        second,
    ]
    assert sort_search_results(
        [first, second], "source", True, compact=True
    ) == [second, first]
