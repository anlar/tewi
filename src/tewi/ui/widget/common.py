from textual.reactive import reactive
from textual.widgets import Static, Label
from ...util.decorator import log_time
from ...util.print import print_speed


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
            return ''


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
        # hide indicator when single page
        if self.state is None or self.state.total == 1:
            return ''
        else:
            # include padding by spaces
            return f' [ {self.state.current + 1} / {self.state.total} ] '
