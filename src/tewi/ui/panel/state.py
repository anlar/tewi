from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import Grid
from textual.reactive import reactive

from ..widget.common import ReactiveLabel, PageIndicator, SpeedIndicator

from ...util.print import print_size
from ...util.decorator import log_time


class StatePanel(Static):

    r_session = reactive(None)

    # recompose whole line to update blocks width
    r_page = reactive(None, recompose=True)
    r_stats = reactive('', recompose=True)
    r_sort = reactive('', recompose=True)
    r_alt_speed = reactive('', recompose=True)
    r_alt_delimiter = reactive('', recompose=True)

    r_stats_size = reactive('', recompose=True)

    r_upload_speed = reactive(0)
    r_download_speed = reactive(0)

    @log_time
    def compose(self) -> ComposeResult:
        with Grid(id="state-panel"):
            yield PageIndicator(classes="column page").data_bind(
                    state=StatePanel.r_page)
            yield ReactiveLabel(classes="column").data_bind(
                    name=StatePanel.r_stats)
            yield ReactiveLabel(classes="column").data_bind(
                    name=StatePanel.r_stats_size)
            yield ReactiveLabel(classes="column sort").data_bind(
                    name=StatePanel.r_sort)
            yield Static("", classes="column")
            yield ReactiveLabel(classes="column alt-speed").data_bind(
                    name=StatePanel.r_alt_speed)
            yield ReactiveLabel(classes="column delimiter").data_bind(
                    name=StatePanel.r_alt_delimiter)
            yield Static("↑", classes="column arrow")
            yield SpeedIndicator(classes="column").data_bind(
                    speed=StatePanel.r_upload_speed)
            yield Static("↓", classes="column arrow")
            yield SpeedIndicator(classes="column").data_bind(
                    speed=StatePanel.r_download_speed)

    @log_time
    def watch_r_session(self, new_r_session):
        if new_r_session:
            self.r_stats = self.print_stats(new_r_session)

            complete_size = print_size(new_r_session['torrents_complete_size'])
            total_size = print_size(new_r_session['torrents_total_size'])

            if complete_size < total_size:
                self.r_stats_size = f'Size: {complete_size} / {total_size}'
            else:
                self.r_stats_size = f'Size: {complete_size}'

            sort_order = new_r_session['sort_order'].name
            sort_order_asc = new_r_session['sort_order_asc']
            sort_arrow = '' if sort_order_asc else '↑'
            self.r_sort = f'Sort: {sort_order}{sort_arrow}'

            self.r_upload_speed = new_r_session['upload_speed']
            self.r_download_speed = new_r_session['download_speed']
            alt_speed_enabled = new_r_session['alt_speed_enabled']
            alt_speed_up = new_r_session['alt_speed_up']
            alt_speed_down = new_r_session['alt_speed_down']

            if alt_speed_enabled:
                self.r_alt_speed = f'Speed Limits: ↑ {alt_speed_up} KB ↓ {alt_speed_down} KB'
                self.r_alt_delimiter = '»»»'
            else:
                self.r_alt_speed = ''
                self.r_alt_delimiter = ''

    def print_stats(self, session) -> str:
        stats = f"Torrents: {session['torrents_count']}"

        statuses = []

        if session['torrents_down'] > 0:
            statuses.append(f"Downloading: {session['torrents_down']}")

        if session['torrents_seed'] > 0:
            statuses.append(f"Seeding: {session['torrents_seed']}")

        if session['torrents_check'] > 0:
            statuses.append(f"Verifying: {session['torrents_check']}")

        if session['torrents_stop'] > 0:
            statuses.append(f"Paused: {session['torrents_stop']}")

        if len(statuses) > 0:
            stats = f"{stats} ({', '.join(statuses)})"

        return stats
