"""Sort web search results by the columns shown in the results table."""

from dataclasses import dataclass
from typing import Callable

from .models import SearchResult


@dataclass(frozen=True)
class SearchSortOption:
    key: str
    name: str
    hotkey: str
    value: Callable[[SearchResult], str | int | float | None]


SEARCH_SORT_OPTIONS = (
    SearchSortOption("source", "Source", "p", lambda r: r.provider.casefold()),
    SearchSortOption(
        "uploaded",
        "Uploaded",
        "u",
        lambda r: r.upload_date.timestamp() if r.upload_date else None,
    ),
    SearchSortOption("seeders", "Seeders", "s", lambda r: r.seeders),
    SearchSortOption("leechers", "Leechers", "l", lambda r: r.leechers),
    SearchSortOption("downloads", "Downloads", "d", lambda r: r.downloads),
    SearchSortOption("size", "Size", "z", lambda r: r.size),
    SearchSortOption("files", "Files", "f", lambda r: r.files_count),
    SearchSortOption(
        "category",
        "Category",
        "c",
        lambda r: (
            r.categories[0].full_name.casefold() if r.categories else None
        ),
    ),
    SearchSortOption("name", "Name", "n", lambda r: r.title.casefold()),
)


def get_search_sort_option(key: str) -> SearchSortOption:
    return next(option for option in SEARCH_SORT_OPTIONS if option.key == key)


def sort_search_results(
    results: list[SearchResult],
    key: str,
    ascending: bool,
    *,
    compact: bool = False,
) -> list[SearchResult]:
    """Return a stable ordering with unavailable values last."""
    option = get_search_sort_option(key)
    available = []
    unavailable = []

    for result in results:
        if key == "source" and compact:
            value = (result.provider_short or result.provider).casefold()
        else:
            value = option.value(result)
        if value is None:
            unavailable.append(result)
        else:
            available.append((value, result))

    available.sort(key=lambda item: item[0], reverse=not ascending)
    return [result for _, result in available] + unavailable
