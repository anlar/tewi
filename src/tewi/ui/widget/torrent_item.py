#!/usr/bin/env python3

# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2024  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Renderers of torrent list items.

Torrent list draws items line by line (see TorrentListViewPanel), so items
are not widgets: renderer converts torrent into fixed number of lines made
of Rich segments. Styles are resolved by name through callback provided by
the list, which maps them to its component classes.
"""

import math
from collections.abc import Callable
from typing import ClassVar

from rich.cells import cell_len, set_cell_size
from rich.segment import Segment
from rich.style import Style

from ...torrent.models import Torrent
from ..util import print_ratio, print_size, print_speed, print_time

StyleGetter = Callable[[str], Style]
Line = list[Segment]

STATUS_KIND = {
    "download pending": "download",
    "downloading": "download",
    "seed pending": "seed",
    "seeding": "seed",
    "check pending": "check",
    "checking": "check",
    "stopped": "stop",
}

STATUS_ICON = {
    "download": "▼",
    "seed": "▲",
    "check": "◐",
    "stop": "■",
    "unknown": "?",
}

# Column widths in cells
PAD = 1
GAP = 2
QUEUE_GAP = 2  # between status icon and queue position
PROGRESS_WIDTH = 4
SIZE_WIDTH = 8
RATIO_WIDTH = 5
SPEED_WIDTH = 9
SPEED_GAP = 3  # between ratio and speeds
NAME_MIN_WIDTH = 10
BAR_WIDTH = 40


def fit(text: str, width: int) -> str:
    """Pad or truncate text to exact cell width, marking cut with ellipsis."""
    if width <= 0:
        return ""

    if cell_len(text) <= width:
        return set_cell_size(text, width)

    return set_cell_size(text, width - 1) + "…"


def line_width(line: Line) -> int:
    """Return width of line in cells."""
    return sum(segment.cell_length for segment in line)


def status_kind(status: str) -> str:
    """Return status group used to select icon and style."""
    return STATUS_KIND.get(status, "unknown")


def percent(progress: float) -> int:
    """Convert progress (0..1) to percent, rounding down."""
    # round() removes float error, e.g. 0.29 * 100 = 28.999999999999996
    return math.floor(round(progress * 100, 6))


def queue_width(torrents: list[Torrent]) -> int:
    """Return width of the largest queue position, 0 if there are none."""
    return max(
        (
            len(print_queue(t.queue_position))
            for t in torrents
            if t.queue_position is not None
        ),
        default=0,
    )


def print_queue(position: int | None) -> str:
    return str(position) if position is not None else ""


def print_item_ratio(ratio: float | None) -> str:
    if ratio is None or ratio < 0:
        return "-"
    elif ratio >= 100 and not math.isinf(ratio):
        return print_ratio(ratio, ndigits=0)
    else:
        return print_ratio(ratio, ndigits=1)


def print_stats(torrent: Torrent) -> str:
    peers = torrent.peers_connected

    parts = [
        f"{peers} {'peer' if peers == 1 else 'peers'}",
        f"{torrent.peers_sending_to_us} seed",
        f"{torrent.peers_getting_from_us} leech",
    ]

    eta = torrent.eta
    if eta and eta.total_seconds() > 0:
        eta_str = print_time(eta.total_seconds(), abbr=True, units=2)
        parts.insert(0, f"ETA: {eta_str}")

    return " • ".join(parts)


class TorrentItemRenderer:
    """Base class for torrent list item renderers."""

    height: ClassVar[int] = 1
    """Number of lines in rendered item."""

    def __init__(self, badge_max_count: int = 3, badge_max_length: int = 10):
        """
        Args:
            badge_max_count: Maximum number of category and label badges
                (-1: unlimited, 0: none).
            badge_max_length: Maximum length of badge text (0: unlimited).
        """
        self.badge_max_count = badge_max_count
        self.badge_max_length = badge_max_length

        self.queue_width = 0
        """Width of queue position column, see queue_width()."""

    def render(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> list[Line]:
        """Render torrent into list of `height` lines.

        Lines may be shorter or longer than width: list pads or crops them.
        """
        raise NotImplementedError


class OnelineRenderer(TorrentItemRenderer):
    """Single line: state, name, progress, size, ratio and speeds."""

    height = 1

    def render(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> list[Line]:
        return [self.main_line(torrent, width, style)]

    def main_line(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> Line:
        left = self.state_segments(torrent, style)
        right = self.info_segments(torrent, style)
        right += self.speed_segments(torrent, style)

        fixed = line_width(left + right)
        name_width = max(NAME_MIN_WIDTH, width - fixed - GAP)

        name = [
            Segment(fit(torrent.name, name_width), style("name")),
            Segment(" " * GAP),
        ]

        return left + name + right

    def info_end(self, torrent: Torrent, width: int, style: StyleGetter) -> int:
        """Return position where info column (name to ratio) ends."""
        return width - line_width(self.speed_segments(torrent, style))

    def state_segments(self, torrent: Torrent, style: StyleGetter) -> Line:
        kind = status_kind(torrent.status)

        priority = torrent.priority
        if priority and priority > 0:
            prio = Segment("⇡", style("priority-high"))
        elif priority and priority < 0:
            prio = Segment("⇣", style("priority-low"))
        else:
            prio = Segment(" ")

        return [
            Segment(" " * PAD),
            Segment(STATUS_ICON[kind], style(f"status-{kind}")),
            self.queue_segment(torrent, style),
            prio,
            Segment(" " * GAP),
        ]

    def queue_segment(self, torrent: Torrent, style: StyleGetter) -> Segment:
        """Queue position, aligned by the largest position in the list."""
        if not self.queue_width:
            return Segment(" ")

        queue = print_queue(torrent.queue_position).rjust(self.queue_width)
        return Segment(" " * QUEUE_GAP + queue, style("muted"))

    @property
    def info_start(self) -> int:
        """Return position where info column (name) starts."""
        queue = QUEUE_GAP + self.queue_width if self.queue_width else 1
        # padding, status icon, queue, priority, gap
        return PAD + 1 + queue + 1 + GAP

    def info_segments(self, torrent: Torrent, style: StyleGetter) -> Line:
        pct = percent(torrent.percent_done)
        progress = f"{pct}%".rjust(PROGRESS_WIDTH)

        size = ""
        if torrent.size_when_done is not None:
            size = print_size(torrent.size_when_done, ndigits=1)

        return [
            Segment(progress, style("muted") if pct >= 100 else None),
            Segment(" " * GAP),
            Segment(size.rjust(SIZE_WIDTH)),
            Segment(" " * GAP),
            Segment("R: ", style("muted")),
            Segment(print_item_ratio(torrent.ratio).rjust(RATIO_WIDTH)),
        ]

    def speed_segments(self, torrent: Torrent, style: StyleGetter) -> Line:
        return self.transfer_column(
            self.speed_block("↑", torrent.rate_upload, "speed-up", style),
            self.speed_block("↓", torrent.rate_download, "speed-down", style),
        )

    def speed_block(
        self, arrow: str, speed: int, name: str, style: StyleGetter
    ) -> Line:
        """Arrow and speed; active speed is highlighted with background."""
        text = print_speed(speed, dash_for_zero=True).ljust(SPEED_WIDTH)

        if not speed:
            return [Segment(f" {arrow} {text}")]

        block = style(name)
        return [
            Segment(" ", block),
            Segment(arrow, block + style(f"{name}-arrow")),
            Segment(f" {text}", block + style("speed-active")),
        ]

    def transfer_column(self, upload: Line, download: Line) -> Line:
        """Last column: upload and download blocks.

        Each block is padded value of SPEED_WIDTH with arrow before it, so
        values in different lines (speeds, transferred sizes) are aligned.
        """
        return [
            Segment(" " * SPEED_GAP),
            *upload,
            *download,
            Segment(" " * PAD),
        ]


class CompactRenderer(OnelineRenderer):
    """Oneline item with second line: progress bar, status, peers, badges
    and transferred sizes."""

    height = 2

    def render(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> list[Line]:
        return [
            self.main_line(torrent, width, style),
            self.stats_line(torrent, width, style),
        ]

    def stats_line(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> Line:
        kind = status_kind(torrent.status)

        left = [
            Segment(" " * self.info_start),
            *self.stats_prefix(torrent, style),
            Segment(torrent.status, style(f"status-{kind}")),
            Segment(" " * GAP),
        ]

        stats = print_stats(torrent)
        badges = self.badge_segments(torrent, style)

        # Stats fill info column up to its right edge (above it is ratio),
        # badges are aligned to that edge, stats are truncated if needed
        info_end = self.info_end(torrent, width, style)
        stats_width = info_end - line_width(left)
        if badges:
            stats_width -= line_width(badges) + GAP
            badges = [Segment(" " * GAP), *badges]

        return [
            *left,
            Segment(fit(stats, stats_width), style("muted")),
            *badges,
            *self.stats_suffix(torrent, style),
        ]

    def stats_prefix(self, torrent: Torrent, style: StyleGetter) -> Line:
        """Segments drawn in stats line before torrent status."""
        return [
            *self.bar_segments(torrent.percent_done, BAR_WIDTH, style),
            Segment(" " * GAP),
        ]

    def stats_suffix(self, torrent: Torrent, style: StyleGetter) -> Line:
        """Segments drawn in stats line after info column (under speeds)."""
        return self.transferred_segments(torrent, style)

    def transferred_segments(
        self, torrent: Torrent, style: StyleGetter
    ) -> Line:
        """Uploaded and downloaded sizes, placed under speeds."""

        def size(value: int | None) -> Line:
            text = print_size(value, ndigits=1) if value else ""
            # same layout as speed block, without arrow
            return [Segment(f"   {text.ljust(SPEED_WIDTH)}", style("muted"))]

        downloaded = None
        if torrent.size_when_done is not None:
            downloaded = torrent.size_when_done - torrent.left_until_done

        return self.transfer_column(
            size(torrent.uploaded_ever), size(downloaded)
        )

    def badge_segments(self, torrent: Torrent, style: StyleGetter) -> Line:
        """Category and label badges, limited by count and text length."""
        badges = []

        if torrent.category:
            badges.append((torrent.category, "badge-category"))

        if torrent.labels:
            badges.extend((label, "badge-label") for label in torrent.labels)

        max_count = self.badge_max_count
        if max_count == 0 or not badges:
            return []

        if max_count > 0 and len(badges) > max_count:
            remaining = len(badges) - max_count
            badges = badges[:max_count]
        else:
            remaining = 0

        badges = [(f" {self.trim_badge(text)} ", name) for text, name in badges]

        if remaining:
            badges.append((f" +{remaining} ", "badge-label"))

        result = []
        for i, (text, name) in enumerate(badges):
            if i > 0:
                result.append(Segment(" "))
            result.append(Segment(text, style(name)))

        return result

    def trim_badge(self, text: str) -> str:
        max_length = self.badge_max_length
        if max_length > 0 and cell_len(text) > max_length:
            return set_cell_size(text, max_length) + "…"

        return text

    def bar_segments(
        self, progress: float, width: int, style: StyleGetter
    ) -> Line:
        # Bar is drawn with half-cell precision: last complete cell may be
        # filled only by its left half
        width = max(0, width)
        halves = min(width * 2, max(0, round(progress * width * 2)))
        full, half = divmod(halves, 2)

        bar_style = "bar-finished" if progress >= 1 else "bar-complete"

        return [
            Segment("━" * full + "╸" * half, style(bar_style)),
            Segment("━" * (width - full - half), style("bar-remaining")),
        ]


class CardRenderer(CompactRenderer):
    """Oneline item with progress bar across info column and stats line."""

    height = 4

    def render(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> list[Line]:
        return [
            self.main_line(torrent, width, style),
            self.bar_line(torrent, width, style),
            self.stats_line(torrent, width, style),
            [],  # spacing between cards
        ]

    def bar_line(
        self, torrent: Torrent, width: int, style: StyleGetter
    ) -> Line:
        bar_width = self.info_end(torrent, width, style) - self.info_start

        return [
            Segment(" " * self.info_start),
            *self.bar_segments(torrent.percent_done, bar_width, style),
            *self.transferred_segments(torrent, style),
        ]

    def stats_prefix(self, torrent: Torrent, style: StyleGetter) -> Line:
        # progress bar has its own line
        return []

    def stats_suffix(self, torrent: Torrent, style: StyleGetter) -> Line:
        # transferred sizes are in progress bar line
        return []


RENDERERS: dict[str, type[TorrentItemRenderer]] = {
    "oneline": OnelineRenderer,
    "compact": CompactRenderer,
    "card": CardRenderer,
}


def create_renderer(
    view_mode: str, badge_max_count: int = 3, badge_max_length: int = 10
) -> TorrentItemRenderer:
    return RENDERERS[view_mode](badge_max_count, badge_max_length)
