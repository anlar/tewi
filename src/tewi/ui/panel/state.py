from textual.app import ComposeResult
from textual.containers import Grid
from textual.reactive import reactive
from textual.widgets import Static

from ...util.log import log_time
from ..models import FilterState, SortOrder
from ..util import esc_trunk, print_size, print_speed
from ..widget.common import PageIndicator, ReactiveLabel, SpeedIndicator


class StatePanel(Static):
    r_session = reactive(None)
    r_sort_order = reactive(None)
    r_sort_order_asc = reactive(None)
    r_filter_state = reactive(None)

    # recompose whole line to update blocks width
    r_search = reactive(None, recompose=True)
    r_page = reactive(None, recompose=True)
    r_stats = reactive("", recompose=True)
    r_sort = reactive("", recompose=True)
    r_filter = reactive("", recompose=True)
    r_speed_limit = reactive("", recompose=True)
    r_speed_limit_delimiter = reactive("", recompose=True)

    r_upload_speed = reactive(0)
    r_download_speed = reactive(0)

    @log_time
    def compose(self) -> ComposeResult:
        yield ReactiveLabel(classes="search").data_bind(
            name=StatePanel.r_search
        )
        with Grid(id="state-panel"):
            yield PageIndicator(classes="column page").data_bind(
                state=StatePanel.r_page
            )
            yield ReactiveLabel(classes="column", markup=True).data_bind(
                name=StatePanel.r_stats
            )
            yield ReactiveLabel(classes="column sort").data_bind(
                name=StatePanel.r_sort
            )
            yield ReactiveLabel(id="filter", classes="column filter").data_bind(
                name=StatePanel.r_filter
            )
            yield Static("", classes="column")
            yield ReactiveLabel(
                id="speed-limit", classes="column speed-limit"
            ).data_bind(name=StatePanel.r_speed_limit)
            yield ReactiveLabel(classes="column delimiter").data_bind(
                name=StatePanel.r_speed_limit_delimiter
            )
            yield Static("↑", classes="column arrow")
            yield SpeedIndicator(classes="column").data_bind(
                speed=StatePanel.r_upload_speed
            )
            yield Static("↓", classes="column arrow")
            yield SpeedIndicator(classes="column").data_bind(
                speed=StatePanel.r_download_speed
            )

    @log_time
    def watch_r_sort_order(self, new_r_sort_order: SortOrder) -> None:
        if new_r_sort_order:
            self.update_sort(new_r_sort_order, self.r_sort_order_asc)

    @log_time
    def watch_r_sort_order_asc(self, new_r_sort_order_asc: bool) -> None:
        if new_r_sort_order_asc is not None:
            self.update_sort(self.r_sort_order, new_r_sort_order_asc)

    @log_time
    def watch_r_filter_state(self, new_r_filter_state: FilterState) -> None:
        if new_r_filter_state:
            parts = []

            if new_r_filter_state.option.id != "all":
                parts.append(new_r_filter_state.option.name)

            if new_r_filter_state.name:
                name = esc_trunk(new_r_filter_state.name, 10)
                parts.append(f'"{name}"')

            if parts:
                self.r_filter = (
                    f"Filter: {' + '.join(parts)} "
                    f"({new_r_filter_state.torrent_count})"
                )
                return

        self.r_filter = ""

    @log_time
    def update_sort(self, sort_order: SortOrder, sort_order_asc: bool) -> None:
        sort_arrow = "" if sort_order_asc else " ↑"
        self.r_sort = f"Sort: {sort_order.name}{sort_arrow}"

    @log_time
    def watch_r_session(self, new_r_session):
        if new_r_session:
            self.r_stats = self.print_stats(new_r_session)

            self.r_upload_speed = new_r_session["upload_speed"]
            self.r_download_speed = new_r_session["download_speed"]

            alt_speed_enabled = new_r_session["alt_speed_enabled"]
            alt_speed_up_bytes = new_r_session["alt_speed_up"]
            alt_speed_down_bytes = new_r_session["alt_speed_down"]

            speed_limit_up = new_r_session["speed_limit_up"]
            speed_limit_down = new_r_session["speed_limit_down"]

            if alt_speed_enabled:
                up = print_speed(alt_speed_up_bytes)
                down = print_speed(alt_speed_down_bytes)
                self.r_speed_limit = f"Turtle: ↑ {up} ↓ {down}"
                self.r_speed_limit_delimiter = "»»»"

            elif speed_limit_up or speed_limit_down:
                parts = [
                    p
                    for p in (
                        f"↑ {print_speed(speed_limit_up)}"
                        if speed_limit_up is not None
                        else None,
                        f"↓ {print_speed(speed_limit_down)}"
                        if speed_limit_down is not None
                        else None,
                    )
                    if p is not None
                ]
                self.r_speed_limit = f"Limit: {' '.join(parts)}"
                self.r_speed_limit_delimiter = "»»»"

            else:
                self.r_speed_limit = ""
                self.r_speed_limit_delimiter = ""

    @log_time
    def watch_r_speed_limit(self, new_value):
        if new_value:
            self.remove_class("speed-limit-none")
        else:
            self.add_class("speed-limit-none")

    @log_time
    def watch_r_filter(self, new_value):
        if new_value:
            self.remove_class("filter-none")
        else:
            self.add_class("filter-none")

    @log_time
    def print_stats(self, session) -> str:
        stats = f"Total: {session['torrents_count']}"

        statuses = []

        if session["torrents_check"] > 0:
            statuses.append(f"Verify: {session['torrents_check']}")

        if session["torrents_down"] > 0:
            statuses.append(f"Down: {session['torrents_down']}")

        if session["torrents_seed"] > 0:
            statuses.append(f"Seed: {session['torrents_seed']}")

        if session["torrents_stop"] > 0:
            statuses.append(f"Pause: {session['torrents_stop']}")

        if len(statuses) > 0:
            stats = f"{stats} [dim]|[/] {', '.join(statuses)}"

        complete_size = print_size(session["torrents_complete_size"])
        total_size = print_size(session["torrents_total_size"])

        if complete_size < total_size:
            stats = f"{stats} [dim]|[/] Size: {complete_size} / {total_size}"
        else:
            stats = f"{stats} [dim]|[/] Size: {complete_size}"

        return stats
