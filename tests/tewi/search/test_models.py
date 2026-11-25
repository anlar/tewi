import pytest

from src.tewi.search.models import SearchResult


def result(info_hash: str | None = "a" * 40, **counts) -> SearchResult:
    return SearchResult(
        title="Title",
        info_hash=info_hash,
        magnet_link=None,
        torrent_link=None,
        provider="Provider",
        provider_id="test",
        provider_short="Prov",
        **counts,
    )


class TestSearchResultInfoHash:
    def test_hex_is_lowercased(self):
        assert result(info_hash="A" * 40).info_hash == "a" * 40

    def test_base32_is_converted_to_hex(self):
        assert result(info_hash="A" * 32).info_hash == "00" * 20

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_blank_hash_is_none(self, value):
        assert result(info_hash=value).info_hash is None

    def test_malformed_hash_is_kept(self):
        # Kept as is to be rejected by search manager
        assert result(info_hash="abc").info_hash == "abc"
