"""Tests for search manager."""

from src.tewi.search.base import BaseSearchProvider
from src.tewi.search.manager import SearchClient
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
