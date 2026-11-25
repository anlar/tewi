# SPDX-FileCopyrightText: 2026 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for web search result details dialog."""

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Link

from src.tewi.search.models import DetailsLink, DetailsSection, SearchResult
from src.tewi.ui.dialog.search.details import TorrentDetailsWidget

# OSC 2 (set window title) and CSI (set color) sequences
OSC = "\x1b]2;pwned\x1b\\"
CSI = "\x1b[31m"

MARKUP = "[@click=app.pwn()]x[/]"


class DetailsApp(App):
    CSS_PATH = str(Path(__file__).parents[5] / "src" / "tewi" / "app.tcss")

    def __init__(
        self,
        common: list[DetailsSection],
        extended: list[DetailsSection],
        title: str = "Title",
        page_url: str = "https://example.org/",
    ) -> None:
        super().__init__()
        self.common = common
        self.extended = extended
        self.details_title = title
        self.page_url = page_url

    def compose(self) -> ComposeResult:
        yield TorrentDetailsWidget(
            title=self.details_title,
            page_url=self.page_url,
            common_sections=self.common,
            extended_sections=self.extended,
        )


def render(app: DetailsApp, size: tuple[int, int] = (120, 40)):
    """Run app and return text on screen and Link widgets.

    Returns:
        Tuple of (screen lines, links)
    """
    result = {}

    async def run() -> None:
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            strips = app.screen._compositor.render_strips()
            result["lines"] = [
                "".join(s.text for s in strip) for strip in strips
            ]
            result["links"] = list(app.query(Link))

    asyncio.run(run())
    return result["lines"], result["links"]


def test_control_chars_are_removed():
    """Details come from search providers, so escape sequences in them
    must not reach the terminal: DTOs remove them."""
    result = SearchResult(
        title=f"Title{CSI}",
        info_hash="a" * 40,
        magnet_link=None,
        torrent_link=None,
        provider="Provider",
        provider_id="test",
        provider_short="P",
        page_url=f"https://example.org/{OSC}",
    )
    app = DetailsApp(
        common=[DetailsSection(f"General{CSI}", fields=(("Size", f"1{CSI}"),))],
        extended=[
            DetailsSection(
                "Links", fields=(("IMDB", DetailsLink(f"https://x/{OSC}")),)
            ),
            DetailsSection("Files", items=(f"a{OSC}.mkv",)),
            DetailsSection("Overview", text=f"Plot{OSC} text"),
        ],
        title=result.title,
        page_url=result.page_url,
    )

    lines, links = render(app)
    screen = "\n".join(lines)

    assert "\x1b" not in screen
    assert "Plot]2;pwned\\ text" in screen
    assert [link.url for link in links] == [
        "https://x/]2;pwned\\",
        "https://example.org/]2;pwned\\",
    ]


def test_remote_text_is_shown_literally():
    app = DetailsApp(
        common=[DetailsSection("General", fields=(("Name", MARKUP),))],
        extended=[
            DetailsSection("Files", items=(f"# {MARKUP}",)),
            DetailsSection("Overview", text=f"[x](http://evil) {MARKUP}"),
        ],
    )

    screen = "\n".join(render(app)[0])

    assert f"Name: {MARKUP}" in screen
    assert f"• # {MARKUP}" in screen
    assert f"[x](http://evil) {MARKUP}" in screen


def test_field_values_are_single_line():
    app = DetailsApp(
        common=[DetailsSection("General", fields=(("Name", "a\nb  \tc"),))],
        extended=[],
    )

    assert any("Name: a b c" in line for line in render(app)[0])


def test_long_values_are_aligned_after_labels():
    value = " ".join(["word"] * 30)
    app = DetailsApp(
        common=[
            DetailsSection(
                "General", fields=(("Size", "1 GB"), ("Long label", value))
            )
        ],
        extended=[],
    )

    lines = render(app, size=(80, 40))[0]

    start = next(i for i, line in enumerate(lines) if "Long label:" in line)
    column = lines[start].index("word")
    # Wrapped lines start in the same column as the first one
    assert lines[start + 1][column : column + 4] == "word"
    assert not lines[start + 1][:column].strip("│ ")
    # Value of shorter label starts in the same column
    size_line = next(line for line in lines if "Size:" in line)
    assert size_line.index("1 GB") == column


def test_empty_sections_are_skipped():
    app = DetailsApp(
        common=[
            DetailsSection("Empty"),
            DetailsSection("General", fields=(("Size", "1 GB"),)),
        ],
        extended=[],
    )

    screen = "\n".join(render(app)[0])

    assert "Empty" not in screen
    assert "General" in screen
