import dataclasses

import pytest

from src.tewi.search.models import (
    DetailsLink,
    DetailsSection,
    Indexer,
    StandardCategories,
)

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
            fields=((f"Label{OSC}", f"value{OSC}"),),
            items=(f"a{OSC}.mkv",),
            text=f"line 1{OSC}\n\tline 2",
        )

        assert section == DetailsSection(
            f"Files{CLEAN}",
            fields=((f"Label{CLEAN}", f"value{CLEAN}"),),
            items=(f"a{CLEAN}.mkv",),
            # Line breaks and tabs are kept
            text=f"line 1{CLEAN}\n\tline 2",
        )

    def test_details_section_keeps_links(self):
        link = DetailsLink("https://x/")
        section = DetailsSection("Links", fields=(("IMDB", link),))

        assert section.fields == (("IMDB", link),)


class TestCategory:
    def test_is_immutable(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            StandardCategories.TV.name = "Other"

    def test_full_path(self):
        assert StandardCategories.TV_ANIME.full_path == "TV/Anime"
        assert StandardCategories.TV.full_path == "TV"
