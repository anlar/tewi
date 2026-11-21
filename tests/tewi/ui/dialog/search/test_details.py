"""Tests for web search result details dialog."""

import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Link, Markdown, Static

from src.tewi.ui.dialog.search.details import TorrentDetailsWidget

# OSC 2 (set window title) and CSI (set color) sequences
OSC = "\x1b]2;pwned\x1b\\"
CSI = "\x1b[31m"


class DetailsApp(App):
    def compose(self) -> ComposeResult:
        yield TorrentDetailsWidget(
            title=f"Title{CSI}",
            page_url=f"https://example.org/{OSC}",
            common_content=f"## General\n- **Size:** 1 GB{CSI}\n",
            extended_content=f"## Info\n- **Overview:** Plot{OSC}\ttext\n",
        )


def test_control_chars_are_removed():
    """Details content comes from search providers, partly not via
    SearchResult (e.g. Bitmagnet details loaded on demand), so escape
    sequences in it must not reach the terminal."""

    async def run() -> None:
        app = DetailsApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            common, extended = app.query(Markdown)
            link = app.query_one(Link)
            title = app.query_one(".details-title", Static)

            assert common.source == "## General\n- **Size:** 1 GB[31m\n"
            # Line breaks and tabs are kept
            assert extended.source == (
                "## Info\n- **Overview:** Plot]2;pwned\\\ttext\n"
            )
            assert link.url == "https://example.org/]2;pwned\\"
            assert link.text == link.url
            assert "\x1b" not in str(title.render())

    asyncio.run(run())
