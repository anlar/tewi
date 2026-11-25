import pytest

from src.tewi.search.models import (
    DetailsLink,
    DetailsSection,
    Indexer,
    SearchResult,
)


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


# OSC 2 (set window title) sequence
OSC = "\x1b]2;pwned\x1b\\"
CLEAN = "]2;pwned\\"


class TestControlCharsAreRemoved:
    """Text in search DTOs comes from search providers, so escape
    sequences are removed when DTO is created."""

    def test_indexer(self):
        indexer = Indexer(f"jackett:x{OSC}", f"Name{OSC}", f"J{OSC}")

        assert indexer == Indexer(
            f"jackett:x{CLEAN}", f"Name{CLEAN}", f"J{CLEAN}"
        )

    def test_details_link(self):
        assert DetailsLink(f"https://x/{OSC}").url == f"https://x/{CLEAN}"

    def test_details_section(self):
        section = DetailsSection(
            f"Files{OSC}",
            fields=[(f"Label{OSC}", f"value{OSC}")],
            items=[f"a{OSC}.mkv"],
            text=f"line 1{OSC}\n\tline 2",
        )

        assert section == DetailsSection(
            f"Files{CLEAN}",
            fields=[(f"Label{CLEAN}", f"value{CLEAN}")],
            items=[f"a{CLEAN}.mkv"],
            # Line breaks and tabs are kept
            text=f"line 1{CLEAN}\n\tline 2",
        )

    def test_details_section_keeps_links(self):
        link = DetailsLink("https://x/")
        section = DetailsSection("Links", fields=[("IMDB", link)])

        assert section.fields == [("IMDB", link)]
