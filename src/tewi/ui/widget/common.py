from typing import TypeVar

from textual import on
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import DataTable, Label, SelectionList, Static

from ...util.log import log_time
from ..util import print_speed


class VimDataTable(DataTable):
    BINDINGS = [
        Binding("k", "cursor_up", "Cursor up", show=False),
        Binding("j", "cursor_down", "Cursor down", show=False),
        Binding("l", "cursor_right", "Cursor right", show=False),
        Binding("h", "cursor_left", "Cursor left", show=False),
        Binding("g", "scroll_top", "Home", show=False),
        Binding("G", "scroll_bottom", "End", show=False),
    ]


SelectionType = TypeVar("SelectionType")


class VimSelectionList(SelectionList[SelectionType]):
    """SelectionList with vim-style keybindings.

    Generic type parameter allows type-safe selection values.
    """

    BINDINGS = [
        Binding("k", "cursor_up", "Up", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("g", "first", "First", show=False),
        Binding("G", "last", "Last", show=False),
    ]

    @on(SelectionList.SelectionToggled)
    def update_selected_view(self) -> None:
        self.action_cursor_down()


class ReactiveLabel(Label):
    name = reactive(None, layout=True)

    @log_time
    def __init__(self, *args, markup=False, **kwargs):
        super().__init__(*args, markup=markup, **kwargs)
        self.markup = False

    @log_time
    def render(self):
        if self.name:
            return self.name
        else:
            return ""


class SpeedIndicator(Static):
    speed = reactive(0)

    @log_time
    def watch_speed(self, speed: int) -> None:
        if speed > 0:
            self.add_class("non-zero")
        else:
            self.remove_class("non-zero")

    @log_time
    def render(self) -> str:
        return print_speed(self.speed, dash_for_zero=True)


class PageIndicator(Static):
    state = reactive(None)

    @log_time
    def __init__(self, *args, **kwargs):
        super().__init__(*args, markup=False, **kwargs)

    @log_time
    def render(self) -> str:
        # hide indicator when single page or none (no torrents)
        if self.state is None or self.state.total <= 1:
            return ""
        else:
            # include padding by spaces
            return f" [ {self.state.current + 1} / {self.state.total} ] "
