"""Tests for search manager."""

import base64
import threading
import time

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.manager import SearchClient, resolve_provider_aliases
from src.tewi.search.models import SearchResult

VALID_HASH = "a" * 40


def result(title: str, info_hash: str | None) -> SearchResult:
    return SearchResult(
        title=title,
        info_hash=info_hash,
        magnet_link=None,
        torrent_link="https://example.com/x.torrent",
        provider="Fake",
        provider_id="fake",
        provider_short="F",
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

    def details_extended(self, result: SearchResult) -> str:
        return ""


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


class TestSearchInfoHashValidation:
    def test_results_with_valid_or_missing_hash_are_kept(self):
        found = search(
            [
                result("hex", VALID_HASH),
                result("base32", "A" * 32),
                result("no hash", None),
            ]
        )

        assert [r.title for r in found] == ["hex", "base32", "no hash"]

    def test_results_with_malformed_hash_are_skipped(self):
        found = search(
            [
                result("injected", VALID_HASH + "&tr=udp://attacker:1"),
                result("short", "abc"),
                result("valid", VALID_HASH),
            ]
        )

        assert [r.title for r in found] == ["valid"]

    def test_same_hash_in_different_forms_is_deduplicated(self):
        hex_hash = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
        base32 = base64.b32encode(bytes.fromhex(hex_hash)).decode()
        found = search(
            [
                result("upper", hex_hash.upper()),
                result("lower", hex_hash),
                result("base32", base32),
            ]
        )

        assert [(r.title, r.info_hash) for r in found] == [("upper", hex_hash)]


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
