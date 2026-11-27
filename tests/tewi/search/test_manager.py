# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for search manager."""

import threading
import time
from datetime import datetime, timezone

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.manager import (
    SearchClient,
    merge_results,
    resolve_provider_aliases,
)
from src.tewi.search.models import (
    DetailsSection,
    SearchResult,
    StandardCategories,
)

VALID_HASH = "a" * 40


def result(title: str, info_hash: str | None, **kwargs) -> SearchResult:
    return SearchResult(
        title=title,
        info_hash=info_hash,
        magnet_link=None,
        torrent_link="https://example.com/x.torrent",
        provider="Fake",
        provider_id="fake",
        provider_short="F",
        **kwargs,
    )


class FakeProvider(BaseSearchProvider):
    def __init__(self, results: list[SearchResult]) -> None:
        super().__init__()
        self.results = results

    @property
    def id(self) -> str:
        return "fake"

    @property
    def name(self) -> str:
        return "Fake"

    def search(self, query, categories=None, indexers=None):
        return self.results

    def details_extended(self, result: SearchResult) -> list[DetailsSection]:
        return []


class StalledProvider(FakeProvider):
    """Provider whose search blocks until released."""

    def __init__(self) -> None:
        super().__init__([])
        self.release = threading.Event()

    @property
    def name(self) -> str:
        return "Stalled"

    def search(self, query, categories=None, indexers=None):
        self.release.wait(10)
        return [result("late", VALID_HASH)]


def search(results: list[SearchResult]) -> list[SearchResult]:
    client = SearchClient(None, None, False, None, None, False, None, 30)
    client._providers = [FakeProvider(results)]
    found, errors = client.search("query", None, None)
    assert errors == []
    return found


class TestMergeResults:
    def test_single_result_is_unchanged(self):
        r = result("one", VALID_HASH, seeders=5)
        assert merge_results([r]) is r
        assert r.sources == ()
        assert r.all_sources == (r,)

    def test_sources_are_kept(self):
        results = [result("a", VALID_HASH), result("b", VALID_HASH)]

        merged = merge_results(results)

        assert merged.sources == tuple(results)
        assert merged.all_sources == tuple(results)

    def test_counts_are_max(self):
        merged = merge_results(
            [
                result("a", VALID_HASH, seeders=5, leechers=None, downloads=1),
                result("b", VALID_HASH, seeders=50, leechers=3),
                result("c", VALID_HASH, seeders=0, leechers=7, downloads=9),
            ]
        )

        assert (merged.seeders, merged.leechers, merged.downloads) == (
            50,
            7,
            9,
        )

    def test_missing_counts_stay_none(self):
        merged = merge_results(
            [result("a", VALID_HASH), result("b", VALID_HASH)]
        )

        assert merged.seeders is None
        assert merged.downloads is None

    def test_upload_date_is_earliest(self):
        early = datetime(2021, 2, 23, tzinfo=timezone.utc)
        merged = merge_results(
            [
                result(
                    "a",
                    VALID_HASH,
                    upload_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
                ),
                result("b", VALID_HASH),
                result("c", VALID_HASH, upload_date=early),
            ]
        )

        assert merged.upload_date == early

    def test_files_count_is_from_first_reporting_provider(self):
        merged = merge_results(
            [
                result("a", VALID_HASH),
                result("b", VALID_HASH, files_count=3),
                result("c", VALID_HASH, files_count=10),
            ]
        )

        assert merged.files_count == 3

    def test_other_fields_are_from_first_result(self):
        first = result(
            "first",
            VALID_HASH,
            size=100,
            page_url="https://first",
            extra={"key": "first"},
        )
        merged = merge_results(
            [
                first,
                result(
                    "second",
                    VALID_HASH,
                    size=200,
                    page_url="https://second",
                    extra={"key": "second"},
                ),
            ]
        )

        assert merged.title == "first"
        assert merged.size == 100
        assert merged.page_url == "https://first"
        assert merged.extra == {"key": "first"}

    def test_categories_are_combined(self):
        hd, uhd, tv = (
            StandardCategories.MOVIES_HD,
            StandardCategories.MOVIES_UHD,
            StandardCategories.TV,
        )
        merged = merge_results(
            [
                result("a", VALID_HASH, categories=(hd,)),
                result("b", VALID_HASH, categories=(uhd, hd)),
                result("c", VALID_HASH, categories=(tv,)),
            ]
        )

        assert merged.categories == (hd, uhd, tv)

    def test_category_filter_matches_any_source(self):
        client = SearchClient(None, None, False, None, None, False, None, 30)
        client._providers = [
            FakeProvider(
                [
                    result("a", VALID_HASH),
                    result(
                        "b", VALID_HASH, categories=(StandardCategories.TV_HD,)
                    ),
                ]
            )
        ]

        found, _ = client.search("query", None, [StandardCategories.TV])

        assert [r.title for r in found] == ["a"]

    def test_search_merges_duplicates(self):
        found = search(
            [
                result("first", VALID_HASH, seeders=1, downloads=None),
                result("other", "b" * 40, seeders=2),
                result("second", VALID_HASH, seeders=9, downloads=4),
            ]
        )

        assert [(r.title, r.seeders, r.downloads) for r in found] == [
            ("first", 9, 4),
            ("other", 2, None),
        ]


class TestSearchWithoutHash:
    def test_results_without_hash_are_kept(self):
        found = search([result("a", None, size=1), result("b", VALID_HASH)])

        assert [r.title for r in found] == ["a", "b"]

    def test_results_without_hash_are_deduplicated_by_title_and_size(self):
        found = search(
            [
                result("a", None, size=1, seeders=1),
                result("a", None, size=1, seeders=5),
                result("a", None, size=2),
            ]
        )

        assert [(r.title, r.size, r.seeders) for r in found] == [
            ("a", 1, 5),
            ("a", 2, None),
        ]


class TestProviderAliases:
    def test_retired_id_is_replaced(self):
        assert resolve_provider_aliases(["tpb", "torrentz2"]) == [
            "tpb",
            "bitsearch",
        ]

    def test_duplicates_after_resolving_are_removed(self):
        assert resolve_provider_aliases(["torrentz2", "yts", "bitsearch"]) == [
            "bitsearch",
            "yts",
        ]

    def test_enabled_providers_accept_alias(self):
        client = SearchClient(
            None, None, False, None, None, False, None, 30, ["torrentz2"]
        )
        assert client._enabled_providers == ["bitsearch"]


class TestSearchTimeout:
    def test_stalled_provider_is_abandoned(self):
        client = SearchClient(None, None, False, None, None, False, None, 1)
        stalled = StalledProvider()
        client._providers = [stalled, FakeProvider([result("x", None)])]
        try:
            start = time.monotonic()
            found, errors = client.search("query", None, None)
            elapsed = time.monotonic() - start
        finally:
            stalled.release.set()

        assert elapsed < 5
        assert [r.title for r in found] == ["x"]
        assert errors == ["Stalled: timed out after 1 seconds"]
