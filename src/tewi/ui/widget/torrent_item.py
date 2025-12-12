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

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.reactive import reactive
from textual.widgets import ProgressBar, Static

from ...torrent.models import Torrent
from ...util.log import log_time
from ..util import esc_trunk, print_size, print_time
from .common import ReactiveLabel, SpeedIndicator


class TorrentItem(Static):
    selected = reactive(False)
    marked = reactive(False)
    torrent: Torrent | None = reactive(None)

    t_id = reactive(None)
    t_name = reactive(None)
    t_status = reactive(None)

    t_size_total = reactive(None)
    t_size_left = reactive(None)
    t_ratio = reactive(0)
    t_progress = reactive(0)
    t_eta = reactive(None)

    t_upload_speed = reactive(0)
    t_download_speed = reactive(0)

    t_size_stats = reactive("")
    t_queue_position = reactive(None)
    t_priority = reactive(None)
    t_queue_indicator = reactive("")
    t_priority_indicator = reactive("")

    w_next = None
    w_prev = None

    @log_time
    def __init__(self, torrent: Torrent):
        super().__init__()
        self.update_torrent(torrent)

    @log_time
    def watch_t_status(self, new_t_status):
        # For all other statuses using default colors:
        # - yellow - in progress
        # - green - complete
        self.remove_class("torrent-bar-stop", "torrent-bar-check")

        match new_t_status:
            case "stopped":
                self.add_class("torrent-bar-stop")
            case "check pending" | "checking":
                self.add_class("torrent-bar-check")

    @log_time
    def watch_selected(self, new_selected):
        if new_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    @log_time
    def watch_marked(self, new_marked):
        if new_marked:
            self.add_class("marked")
        else:
            self.remove_class("marked")

    @log_time
    def watch_t_queue_position(self, new_value):
        self.remove_class("position-none", "position-present")
        if new_value is not None:
            self.t_queue_indicator = f"#{new_value}"
            self.add_class("position-present")
        else:
            self.t_queue_indicator = ""
            self.add_class("position-none")

    @log_time
    def watch_t_priority(self, new_value):
        self.remove_class("priority-none", "priority-low", "priority-high")
        if new_value is not None and new_value != 0:
            if new_value > 0:
                self.t_priority_indicator = "⬆"
                self.add_class("priority-high")
            elif new_value < 0:
                self.t_priority_indicator = "⬇"
                self.add_class("priority-low")
        else:
            self.t_priority_indicator = ""
            self.add_class("priority-none")

    @log_time
    def update_torrent(self, torrent: Torrent) -> None:
        with self.app.batch_update():
            self.torrent = torrent

            self.t_id = torrent.hash
            self.t_name = torrent.name
            self.t_status = torrent.status
            self.t_queue_position = torrent.queue_position
            self.t_priority = torrent.priority

            self.t_size_total = torrent.total_size
            self.t_size_left = torrent.left_until_done
            self.t_progress = torrent.percent_done
            self.t_eta = torrent.eta

            self.t_upload_speed = torrent.rate_upload
            self.t_download_speed = torrent.rate_download
            self.t_ratio = torrent.ratio

            self.t_size_stats = self.print_size_stats()

    @log_time
    def print_size_stats(self, full_ratio=True) -> str:
        result = None

        size_total = print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = print_size(self.t_size_total - self.t_size_left)
            progress = self.t_progress * 100
            result = f"{size_current} / {size_total} | {progress:.1f}%"

            if self.t_eta:
                eta = print_time(self.t_eta.total_seconds(), True, 1)
                result = f"{result} | {eta}"
        else:
            result = f"{size_total} | R: {self.t_ratio:.2f}"

        return result


class TorrentItemOneline(TorrentItem):
    @log_time
    def compose(self) -> ComposeResult:
        with Horizontal(id="name-container"):
            yield ReactiveLabel(id="queue", markup=False).data_bind(
                name=TorrentItemOneline.t_queue_indicator
            )
            yield ReactiveLabel(id="priority", markup=False).data_bind(
                name=TorrentItemOneline.t_priority_indicator
            )
            yield ReactiveLabel(id="name", markup=False).data_bind(
                name=TorrentItemOneline.t_name
            )

        with Grid(id="speed"):
            yield ReactiveLabel(id="stats").data_bind(
                name=TorrentItemCompact.t_size_stats
            )
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(
                speed=TorrentItemOneline.t_upload_speed
            )
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(
                speed=TorrentItemOneline.t_download_speed
            )

    @log_time
    def watch_t_status(self, new_t_status):
        self.remove_class(
            "torrent-complete",
            "torrent-incomplete",
            "torrent-stop",
            "torrent-check",
        )

        match new_t_status:
            case "stopped":
                self.add_class("torrent-stop")
            case "check pending" | "checking":
                self.add_class("torrent-check")
            case "download pending" | "downloading":
                self.add_class("torrent-incomplete")
            case "seed pending" | "seeding":
                self.add_class("torrent-complete")


class TorrentItemCompact(TorrentItem):
    @log_time
    def compose(self) -> ComposeResult:
        with Horizontal(id="name-container"):
            yield ReactiveLabel(id="queue", markup=False).data_bind(
                name=TorrentItemCompact.t_queue_indicator
            )
            yield ReactiveLabel(id="priority", markup=False).data_bind(
                name=TorrentItemCompact.t_priority_indicator
            )
            yield ReactiveLabel(id="name", markup=False).data_bind(
                name=TorrentItemCompact.t_name
            )

        with Grid(id="speed"):
            yield ReactiveLabel(id="stats").data_bind(
                name=TorrentItemCompact.t_size_stats
            )
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(
                speed=TorrentItemCompact.t_upload_speed
            )
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(
                speed=TorrentItemCompact.t_download_speed
            )

        yield (
            ProgressBar(
                total=1.0, show_percentage=False, show_eta=False
            ).data_bind(progress=TorrentItemCompact.t_progress)
        )


class TorrentItemCard(TorrentItem):
    t_status_markup = reactive(None)

    t_badges_markup = reactive(None)

    t_stats_uploaded = reactive("")
    t_stats_peer = reactive("")
    t_stats_seed = reactive("")
    t_stats_leech = reactive("")

    @log_time
    def compose(self) -> ComposeResult:
        with Horizontal(id="name-container"):
            yield ReactiveLabel(id="queue", markup=False).data_bind(
                name=TorrentItemCard.t_queue_indicator
            )
            yield ReactiveLabel(id="priority", markup=False).data_bind(
                name=TorrentItemCard.t_priority_indicator
            )
            yield ReactiveLabel(id="name", markup=False).data_bind(
                name=TorrentItemCard.t_name
            )

        with Grid(id="speed"):
            yield ReactiveLabel(markup=True).data_bind(
                name=TorrentItemCard.t_badges_markup
            )
            yield Static(" ↑ ")
            yield SpeedIndicator().data_bind(
                speed=TorrentItemCard.t_upload_speed
            )
            yield Static(" ↓ ")
            yield SpeedIndicator().data_bind(
                speed=TorrentItemCard.t_download_speed
            )

        yield (
            ProgressBar(
                total=1.0, show_percentage=False, show_eta=False
            ).data_bind(progress=TorrentItemCard.t_progress)
        )

        with Grid(id="stats"):
            yield ReactiveLabel(markup=True).data_bind(
                name=TorrentItemCard.t_status_markup
            )
            yield ReactiveLabel().data_bind(
                name=TorrentItemCard.t_stats_uploaded
            )
            yield ReactiveLabel().data_bind(name=TorrentItemCard.t_stats_peer)
            yield ReactiveLabel().data_bind(name=TorrentItemCard.t_size_stats)

    @log_time
    def update_torrent(self, torrent: Torrent) -> None:
        super().update_torrent(torrent)

        with self.app.batch_update():
            self.t_status_markup = self.print_status(torrent.status)

            self.t_badges_markup = self.print_badges(
                torrent.category, torrent.labels
            )

            self.t_eta = torrent.eta
            self.t_peers_connected = torrent.peers_connected
            self.t_leechers = torrent.peers_getting_from_us
            self.t_seeders = torrent.peers_sending_to_us
            self.t_ratio = torrent.ratio
            self.t_priority = torrent.priority

            self.t_stats_uploaded = (
                print_size(torrent.uploaded_ever) + " uploaded"
            )

            # implying that there won't be more than 9999 peers
            self.t_stats_peer = (
                f"{self.t_peers_connected: >4} peers "
                f"{self.t_seeders: >4} seeders "
                f"{self.t_leechers: >4} leechers"
            )

    @log_time
    def print_size_stats(self, full_ratio=True) -> str:
        result = None

        size_total = print_size(self.t_size_total)

        if self.t_size_left > 0:
            size_current = print_size(self.t_size_total - self.t_size_left)
            progress = self.t_progress * 100
            result = f"{size_current} / {size_total} | {progress:.1f}%"

            if self.t_eta:
                result = (
                    f"{result} | {print_time(self.t_eta.total_seconds(), 2)}"
                )
        else:
            result = f"{size_total} | Ratio: {self.t_ratio:.2f}"

        return result

    @log_time
    def print_status(self, status: str) -> str:
        match status:
            case "stopped":
                return "[bold $background-lighten-3]" + status + "[/]"
            case "check pending" | "checking":
                return "[bold $error-darken-1]" + status + "[/]"
            case "download pending" | "downloading":
                return "[bold $primary]" + status + "[/]"
            case "seed pending" | "seeding":
                return "[bold $success]" + status + "[/]"
            case _:
                return "[bold]" + status + "[/]"

    @log_time
    def print_badges(self, category: str | None, labels: list | None) -> str:
        badges = []

        font = "$accent"
        back_c = "$secondary-lighten-3"
        back_l = "$secondary-lighten-2"

        max_length = self.app.badge_max_length

        if category:
            badges.append((esc_trunk(category, max_length), font, back_c))

        if labels:
            badges.extend(
                (esc_trunk(label, max_length), font, back_l) for label in labels
            )

        # Don't draw badges if there are 0 of them or they are disabled
        max_count = self.app.badge_max_count
        if max_count == 0 or not badges:
            return None

        # Trim number of badges to max limit
        original_count = len(badges)
        if max_count > 0:
            badges = badges[:max_count]

        result = " ".join(f"[{f} on {b}] {s} [/]" for s, f, b in badges)

        # Draw others counter (only if badge count was limited)
        if max_count > 0:
            remaining = original_count - max_count
            if remaining > 0:
                result += f" [{font} on {back_l}] +{remaining} [/]"

        return result
