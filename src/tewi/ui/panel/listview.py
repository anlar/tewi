import math
from typing import ClassVar, Optional

from rich.style import Style
from textual import events, on
from textual.binding import Binding, BindingType
from textual.color import Color
from textual.geometry import Region, Size
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

from ...torrent.models import Torrent
from ...util.log import log_time
from ..messages import (
    ChangeTorrentPriorityCommand,
    ClearFiltersCommand,
    Notification,
    OpenAddTorrentCommand,
    OpenEditTorrentCommand,
    OpenFilterCommand,
    OpenFilterNameCommand,
    OpenSearchCommand,
    OpenSortOrderCommand,
    OpenTorrentInfoCommand,
    OpenUpdateTorrentCategoryCommand,
    OpenUpdateTorrentLabelsCommand,
    PageChangedEvent,
    ReannounceTorrentCommand,
    RemoveTorrentCommand,
    SearchStateChangedEvent,
    StartAllTorrentsCommand,
    StopAllTorrentsCommand,
    ToggleTorrentCommand,
    TorrentRemovedEvent,
    TorrentTrashedEvent,
    TrashTorrentCommand,
    VerifyTorrentCommand,
)
from ..models import PageState
from ..widget.torrent_item import (
    TorrentItemRenderer,
    create_renderer,
    queue_width,
)


class TorrentListViewPanel(ScrollView, can_focus=True):
    """Paged torrent list.

    Items are not widgets: list draws only visible lines with Line API
    (render_line), using renderer for current view mode. Rendered items are
    cached and redrawn only when torrent data, width or highlight changes,
    so cost of updates and cursor movement doesn't depend on page size.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "cursor_up", show=False),
        Binding("down", "cursor_down", show=False),
        Binding("k", "cursor_up", "[Navigation] Move up"),
        Binding("j", "cursor_down", "[Navigation] Move down"),
        Binding("g,home", "move_top", "[Navigation] Go to first item"),
        Binding("G,end", "move_bottom", "[Navigation] Go to last item"),
        Binding("ctrl+f,pagedown", "page_down", "[Navigation] Page down"),
        Binding("ctrl+b,pageup", "page_up", "[Navigation] Page up"),
        Binding("ctrl+d", "half_page_down", "[Navigation] Half page down"),
        Binding("ctrl+u", "half_page_up", "[Navigation] Half page up"),
        Binding("enter,l,right", "select_cursor", "[Navigation] Open"),
        Binding("a", "add_torrent", "[Torrent] Add"),
        Binding("e", "edit_torrent", "[Torrent] Edit"),
        Binding("L", "update_torrent_labels", "[Torrent] Update labels"),
        Binding("C", "update_torrent_category", "[Torrent] Set category"),
        Binding("s", "sort_order", "[Torrent] Sort order"),
        Binding("f", "filter", "[Torrent] Filter by state"),
        Binding("F", "filter_name", "[Torrent] Filter by name"),
        Binding("escape", "clear_filters", "[Torrent] Clear filters"),
        Binding("p", "change_priority", "[Torrent] Change priority"),
        Binding("space", "toggle_torrent", "[Torrent] Toggle state"),
        Binding("r", "remove_torrent", "[Torrent] Remove"),
        Binding("R", "trash_torrent", "[Torrent] Trash with data"),
        Binding("v", "verify_torrent", "[Torrent] Verify"),
        Binding("c", "reannounce_torrent", "[Torrent] Reannounce"),
        Binding("y", "start_all_torrents", "[Torrent] Start all"),
        Binding("Y", "stop_all_torrents", "[Torrent] Stop all"),
        Binding("m", "toggle_view_mode", "[UI] Toggle view mode"),
        Binding("/", "search", "[Search] Open"),
        Binding("n", "search_next", "[Search] Next result"),
        Binding("N", "search_previous", "[Search] Previous result"),
    ]

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "torrent-list--cursor",
        "torrent-list--hover",
        "torrent-list--even-row",
        "torrent-list--odd-row",
        "torrent-list--name",
        "torrent-list--muted",
        "torrent-list--status-download",
        "torrent-list--status-seed",
        "torrent-list--status-check",
        "torrent-list--status-stop",
        "torrent-list--status-unknown",
        "torrent-list--priority-high",
        "torrent-list--priority-low",
        "torrent-list--speed-active",
        "torrent-list--speed-up",
        "torrent-list--speed-up-arrow",
        "torrent-list--speed-down",
        "torrent-list--speed-down-arrow",
        "torrent-list--cursor-speed-up",
        "torrent-list--cursor-speed-up-arrow",
        "torrent-list--cursor-speed-down",
        "torrent-list--cursor-speed-down-arrow",
        "torrent-list--bar-complete",
        "torrent-list--bar-finished",
        "torrent-list--bar-remaining",
        "torrent-list--badge-category",
        "torrent-list--badge-label",
        "torrent-list--cursor-badge-category",
        "torrent-list--cursor-badge-label",
    }

    DEFAULT_CSS = """
    TorrentListViewPanel {
        background: $surface;
        overflow-x: hidden;
        /* keep columns in place (and aligned with state panel) whether
           scrollbar is shown or not */
        scrollbar-gutter: stable;

        & > .torrent-list--even-row {
            background: $surface-lighten-1 50%;
        }
        &:dark > .torrent-list--even-row {
            background: $surface-darken-1 40%;
        }
        & > .torrent-list--hover {
            background: $block-hover-background;
        }
        & > .torrent-list--cursor {
            color: $block-cursor-blurred-foreground;
            background: $block-cursor-blurred-background;
            text-style: $block-cursor-blurred-text-style;
        }
        & > .torrent-list--cursor-badge-category {
            color: auto 87%;
            background: $accent 70%;
        }
        & > .torrent-list--cursor-badge-label {
            color: auto 87%;
            background: white 20%;
        }
        &:focus {
            background-tint: $foreground 5%;
            & > .torrent-list--cursor {
                color: $block-cursor-foreground;
                background: $block-cursor-background;
                text-style: $block-cursor-text-style;
            }
        }

        & > .torrent-list--name { text-style: bold; }
        & > .torrent-list--muted { color: $text-muted; }
        & > .torrent-list--status-download { color: $text-warning; }
        & > .torrent-list--status-seed { color: $text-success; }
        & > .torrent-list--status-check { color: $text-accent; }
        & > .torrent-list--status-stop { color: $text-muted; }
        & > .torrent-list--status-unknown {
            color: $text-error;
            text-style: bold;
        }
        & > .torrent-list--priority-high { color: $text-warning; }
        & > .torrent-list--priority-low { color: $text-muted; }
        & > .torrent-list--speed-active { text-style: bold; }
        & > .torrent-list--speed-up { background: $success-muted; }
        & > .torrent-list--speed-up-arrow {
            color: $text-success;
            text-style: bold;
        }
        & > .torrent-list--speed-down { background: $warning-muted; }
        & > .torrent-list--speed-down-arrow {
            color: $text-warning;
            text-style: bold;
        }
        /* on cursor row arrows use contrast color of the block (classes
           cursor-speed-*-arrow are intentionally left empty) */
        & > .torrent-list--cursor-speed-up {
            color: auto 87%;
            background: $success 70%;
        }
        & > .torrent-list--cursor-speed-down {
            color: auto 87%;
            background: $warning 70%;
        }
        /* ANSI colors can't be blended with white tint */
        &:ansi > .torrent-list--cursor-badge-label {
            color: auto 87%;
            background: $secondary;
        }
        /* ANSI themes have no muted colors: arrow color equals background */
        &:ansi > .torrent-list--speed-up,
        &:ansi > .torrent-list--speed-down {
            background: ansi_default;
        }
        & > .torrent-list--bar-complete { color: $warning; }
        & > .torrent-list--bar-finished { color: $success; }
        & > .torrent-list--bar-remaining { color: $foreground 15%; }
        & > .torrent-list--badge-category {
            color: auto 87%;
            background: $accent;
        }
        & > .torrent-list--badge-label {
            color: auto 87%;
            background: $secondary;
        }
    }
    """

    # Highlighted item index on current page. Changes repaint only lines of
    # old and new highlighted items (see watch_index).
    index = reactive[Optional[int]](None, init=False, repaint=False)
    hover_index = reactive[Optional[int]](None, init=False, repaint=False)

    r_torrents: list[Torrent] | None = reactive(None)

    # Search state
    search_term = ""
    search_idx = 0  # search hits starts with 1
    search_active = False

    @log_time
    def __init__(
        self,
        id: str,
        page_size: str,
        view_mode: str,
        capability_set_priority: bool,
        capability_label: bool,
        capability_category: bool,
        badge_max_count: int = 3,
        badge_max_length: int = 10,
    ) -> None:
        self.page_size = page_size
        self.view_mode = view_mode
        self.capability_set_priority = capability_set_priority
        self.capability_label = capability_label
        self.capability_category = capability_category

        self.badge_max_count = badge_max_count
        self.badge_max_length = badge_max_length
        self.queue_width = 0

        self.renderer = self.create_renderer()
        self.page_torrents: list[Torrent] = []
        self.page_state: PageState | None = None

        # item index -> (torrent, width, highlight kind, rendered lines)
        self._item_cache: dict[int, tuple] = {}
        # (component name, item base style) -> resolved style
        self._style_cache: dict[tuple[str, Style], Style] = {}

        super().__init__(id=id)

    @log_time
    def watch_r_torrents(self, new_r_torrents):
        self.update_queue_width(new_r_torrents or [])

        if new_r_torrents:
            self.update_page(torrents=new_r_torrents)
        else:
            self.update_page(torrents=[])

    @log_time
    def next_page(self, forward: bool) -> None:
        hl_torrent_id = self.get_hl_torrent_id()
        next_torrent_id = None

        if hl_torrent_id:
            for i, item in enumerate(self.r_torrents):
                if item.hash == hl_torrent_id:
                    if forward is True:
                        if i + 1 < len(self.r_torrents):
                            next_torrent_id = self.r_torrents[i + 1].hash
                    else:
                        if i > 0:
                            next_torrent_id = self.r_torrents[i - 1].hash

        if next_torrent_id:
            self.update_page(self.r_torrents, next_torrent_id)

    @log_time
    def update_page(
        self,
        torrents: list[Torrent],
        hl_torrent_id: int = None,
        force: bool = False,
    ) -> None:
        if hl_torrent_id is None:
            hl_torrent_id = self.get_hl_torrent_id()

        if hl_torrent_id is None:
            torrent_idx = None
        else:
            torrent_idx = next(
                (
                    i
                    for i, item in enumerate(torrents)
                    if item.hash == hl_torrent_id
                ),
                None,
            )

        if torrent_idx is None:
            page = 0
        else:
            page = torrent_idx // self.page_size

        self.draw_page(torrents, page, hl_torrent_id, force)

    @log_time
    def draw_page(self, torrents, page, torrent_id, force) -> None:
        """Show page of torrents.

        Only visible lines are repainted, and each of them is taken from
        cache unless its torrent has changed.
        """
        start = page * self.page_size
        self.page_torrents = torrents[start : start + self.page_size]

        if force:
            self._item_cache.clear()
        else:
            self._prune_cache()

        hl_idx = next(
            (
                i
                for i, t in enumerate(self.page_torrents)
                if t.hash == torrent_id
            ),
            None,
        )

        self._update_virtual_size()
        self.index = self.validate_index(hl_idx)
        self.refresh()

        # page change resets scroll, so scroll to cursor after layout
        self.call_after_refresh(self._scroll_to_cursor)

        state = PageState(current=page, total=self.total_pages(torrents))
        if force or state != self.page_state:
            self.page_state = state
            self.post_message(PageChangedEvent(state))

    @log_time
    def total_pages(self, torrents) -> int:
        if len(torrents) == 0:
            return 0
        else:
            return math.ceil(len(torrents) / self.page_size)

    def create_renderer(self) -> TorrentItemRenderer:
        renderer = create_renderer(
            self.view_mode, self.badge_max_count, self.badge_max_length
        )
        renderer.queue_width = self.queue_width
        return renderer

    def update_queue_width(self, torrents: list[Torrent]) -> None:
        """Fit queue column to the largest queue position in the list."""
        width = queue_width(torrents)

        if width != self.queue_width:
            self.queue_width = width
            self.renderer.queue_width = width
            self._item_cache.clear()

    def validate_index(self, index: Optional[int]) -> Optional[int]:
        """Clamp index to current page; highlight first item by default."""
        if not self.page_torrents:
            return None

        if index is None:
            return 0

        return min(max(index, 0), len(self.page_torrents) - 1)

    # Rendering

    def render_line(self, y: int) -> Strip:
        height = self.renderer.height
        width = self.scrollable_content_region.width

        idx, line = divmod(self.scroll_offset.y + y, height)

        if idx >= len(self.page_torrents):
            return Strip.blank(width, self.rich_style)

        return self._render_item(idx, width)[line]

    def _render_item(self, idx: int, width: int) -> list[Strip]:
        torrent = self.page_torrents[idx]

        if idx == self.index:
            kind = "cursor"
        elif idx == self.hover_index:
            kind = "hover"
        elif idx % 2:
            kind = "odd-row"
        else:
            kind = "even-row"

        cached = self._item_cache.get(idx)
        if cached is not None:
            c_torrent, c_width, c_kind, strips = cached
            if c_width == width and c_kind == kind and c_torrent == torrent:
                return strips

        base = self.get_component_rich_style(f"torrent-list--{kind}")

        def style(name: str) -> Style:
            # Item may override component style for itself, e.g. use
            # "cursor-badge-label" instead of "badge-label" for cursor
            override = f"{kind}-{name}"
            if f"torrent-list--{override}" in self.COMPONENT_CLASSES:
                name = override
            return self._component_style(name, base)

        lines = self.renderer.render(torrent, width, style)
        strips = [
            Strip(line).apply_style(base).adjust_cell_length(width, base)
            for line in lines
        ]

        self._item_cache[idx] = (torrent, width, kind, strips)
        return strips

    def _component_style(self, name: str, base: Style) -> Style:
        """Return component style with colors blended over item background.

        Theme colors may be semi-transparent (e.g. $text-muted), while Rich
        styles can't express transparency, so blend them explicitly.
        """
        key = (name, base)
        if (style := self._style_cache.get(key)) is not None:
            return style

        styles = self.get_component_styles(f"torrent-list--{name}")
        style = styles.text_style

        background = Color.from_rich_color(base.bgcolor)

        if styles.has_rule("background"):
            background += styles.background
            style += Style(bgcolor=background.rich_color)

        if styles.has_rule("color"):
            if styles.auto_color:
                contrast = background.get_contrast_text(styles.color.a)
                color = background + contrast
            else:
                color = background + styles.color
            style += Style(color=color.rich_color)

        self._style_cache[key] = style
        return style

    def _prune_cache(self) -> None:
        count = len(self.page_torrents)
        for idx in [i for i in self._item_cache if i >= count]:
            del self._item_cache[idx]

    def _update_virtual_size(self) -> None:
        height = len(self.page_torrents) * self.renderer.height
        self.virtual_size = Size(self.scrollable_content_region.width, height)

    def _refresh_item(self, idx: Optional[int]) -> None:
        if idx is not None:
            height = self.renderer.height
            self.refresh_lines(idx * height, height)

    def _scroll_to_cursor(self) -> None:
        if self.index is not None:
            height = self.renderer.height
            self.scroll_to_region(
                Region(0, self.index * height, 1, height),
                animate=False,
                force=True,
            )

    def watch_index(
        self, old_index: Optional[int], new_index: Optional[int]
    ) -> None:
        self._refresh_item(old_index)
        self._refresh_item(new_index)
        self._scroll_to_cursor()

    def watch_hover_index(
        self, old_index: Optional[int], new_index: Optional[int]
    ) -> None:
        self._refresh_item(old_index)
        self._refresh_item(new_index)

    def notify_style_update(self) -> None:
        # theme or focus changed: cached items have outdated styles
        self._item_cache.clear()
        self._style_cache.clear()
        super().notify_style_update()

    def on_resize(self, event: events.Resize) -> None:
        self._item_cache.clear()
        self._update_virtual_size()
        self._scroll_to_cursor()

    # Mouse

    def _item_at(self, event: events.MouseEvent) -> Optional[int]:
        offset = event.get_content_offset(self)
        if offset is None:
            return None

        idx = (offset.y + self.scroll_offset.y) // self.renderer.height
        return idx if idx < len(self.page_torrents) else None

    def on_click(self, event: events.Click) -> None:
        if (idx := self._item_at(event)) is not None:
            self.index = idx
            self.action_select_cursor()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        self.hover_index = self._item_at(event)

    def on_leave(self, event: events.Leave) -> None:
        self.hover_index = None

    # Actions

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:
        """Check if an action may run."""
        if action == "change_priority":
            return self.capability_set_priority

        if action == "update_torrent_labels":
            return self.capability_label

        if action == "update_torrent_category":
            return self.capability_category

        return True

    # Actions: movement

    @log_time
    def action_move_top(self) -> None:
        if self.page_torrents:
            self.index = 0

    @log_time
    def action_move_bottom(self) -> None:
        if self.page_torrents:
            self.index = len(self.page_torrents) - 1

    @log_time
    def action_page_down(self) -> None:
        self.move_cursor_by(self.visible_items_count())

    @log_time
    def action_page_up(self) -> None:
        self.move_cursor_by(-self.visible_items_count())

    @log_time
    def action_half_page_down(self) -> None:
        self.move_cursor_by(max(1, self.visible_items_count() // 2))

    @log_time
    def action_half_page_up(self) -> None:
        self.move_cursor_by(-max(1, self.visible_items_count() // 2))

    @log_time
    def visible_items_count(self) -> int:
        """Return number of items that fit into the displayed list area."""
        view_height = self.scrollable_content_region.height
        return max(1, view_height // self.renderer.height)

    @log_time
    def move_cursor_by(self, offset: int) -> None:
        """Move cursor by offset across the whole torrent list, switching
        pages when needed. Target position is clamped to list bounds."""
        if not self.r_torrents:
            return

        hl_torrent = self.get_hl_torrent()
        current = self.torrent_idx(hl_torrent) if hl_torrent else None

        if current is None:
            current = 0

        target = min(max(current + offset, 0), len(self.r_torrents) - 1)

        if target != current:
            self.update_page(self.r_torrents, self.r_torrents[target].hash)

    @log_time
    def action_cursor_down(self) -> None:
        if self.index is None:
            self.index = self.validate_index(None)
        elif self.index == len(self.page_torrents) - 1:
            self.next_page(True)
        else:
            self.index += 1

    @log_time
    def action_cursor_up(self) -> None:
        if self.index is None:
            self.index = self.validate_index(None)
        elif self.index == 0:
            self.next_page(False)
        else:
            self.index -= 1

    @log_time
    def action_select_cursor(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(OpenTorrentInfoCommand(torrent_id))

    # Actions: torrent

    @log_time
    def action_edit_torrent(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenEditTorrentCommand(torrent))

    @log_time
    def action_update_torrent_labels(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenUpdateTorrentLabelsCommand(torrent))

    @log_time
    def action_update_torrent_category(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(OpenUpdateTorrentCategoryCommand(torrent))

    @log_time
    def action_verify_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(VerifyTorrentCommand(torrent_id))

    @log_time
    def action_reannounce_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(ReannounceTorrentCommand(torrent_id))

    @log_time
    def action_toggle_torrent(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(
                ToggleTorrentCommand(torrent.hash, torrent.status)
            )

    @log_time
    def action_remove_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(RemoveTorrentCommand(torrent_id))

    @log_time
    def action_trash_torrent(self) -> None:
        if (torrent_id := self.get_hl_torrent_id()) is not None:
            self.post_message(TrashTorrentCommand(torrent_id))

    @log_time
    def action_add_torrent(self) -> None:
        self.post_message(OpenAddTorrentCommand())

    @log_time
    def action_start_all_torrents(self) -> None:
        self.post_message(StartAllTorrentsCommand())

    @log_time
    def action_stop_all_torrents(self) -> None:
        self.post_message(StopAllTorrentsCommand())

    @log_time
    def action_sort_order(self) -> None:
        self.post_message(OpenSortOrderCommand())

    @log_time
    def action_filter(self) -> None:
        self.post_message(OpenFilterCommand())

    @log_time
    def action_filter_name(self) -> None:
        self.post_message(OpenFilterNameCommand())

    @log_time
    def action_clear_filters(self) -> None:
        self.post_message(ClearFiltersCommand())

    @log_time
    def action_change_priority(self) -> None:
        if (torrent := self.get_hl_torrent()) is not None:
            self.post_message(
                ChangeTorrentPriorityCommand(torrent.hash, torrent.priority)
            )

    @log_time
    def action_toggle_view_mode(self) -> None:
        if self.view_mode == "card":
            self.view_mode = "compact"
        elif self.view_mode == "compact":
            self.view_mode = "oneline"
        elif self.view_mode == "oneline":
            self.view_mode = "card"

        self.renderer = self.create_renderer()
        self.update_page(self.r_torrents or [], force=True)

    # Actions: Search

    @log_time
    def action_search(self) -> None:
        # Reset search state when opening search dialog
        self._reset_search()
        self.post_message(OpenSearchCommand())

    @log_time
    def action_search_next(self) -> None:
        if not self.search_active or not self.search_term:
            self.post_message(Notification("No active search"))
        else:
            self._search_torrent(self.search_term, forward=True)

    @log_time
    def action_search_previous(self) -> None:
        if not self.search_active or not self.search_term:
            self.post_message(Notification("No active search"))
        else:
            self._search_torrent(self.search_term, forward=False)

    @log_time
    def _search_torrent(self, search_term: str, forward: bool = True) -> None:
        if not search_term or not self.r_torrents:
            return

        search_term = search_term.lower()

        # Get current index if there's a selected item
        if (torrent := self.get_hl_torrent()) is not None:
            current_idx = self.torrent_idx(torrent)
        else:
            current_idx = -1

        if current_idx is None:
            current_idx = -1

        # Determine search range based on direction
        if forward:
            # Search from current+1 to end, then from start to current
            range1 = range(current_idx + 1, len(self.r_torrents))
            range2 = range(0, current_idx + 1)
        else:
            # Search from current-1 to start, then from end to current
            range1 = range(current_idx - 1, -1, -1)
            range2 = range(len(self.r_torrents) - 1, current_idx, -1)

        total = sum(1 for i in self.r_torrents if search_term in i.name.lower())

        # First search range
        for i in range1:
            if search_term in self.r_torrents[i].name.lower():
                self._select_found_torrent(i)
                self._update_search_idx(total, forward)
                self.post_message(
                    SearchStateChangedEvent(self.search_idx, total)
                )
                return

        # Second search range (wrap around)
        for i in range2:
            if search_term in self.r_torrents[i].name.lower():
                self._select_found_torrent(i)
                self._update_search_idx(total, forward)
                self.post_message(
                    SearchStateChangedEvent(self.search_idx, total)
                )
                return

        # If no match found, show notification
        self.post_message(Notification(f"No torrents matching '{search_term}'"))

    def _update_search_idx(self, total: int, forward: bool) -> None:
        if forward:
            if self.search_idx == total:
                self.search_idx = 1
            else:
                self.search_idx += 1
        else:
            if self.search_idx == 1:
                self.search_idx = total
            else:
                self.search_idx -= 1

    @log_time
    def _select_found_torrent(self, index: int) -> None:
        self.update_page(self.r_torrents, self.r_torrents[index].hash)

    @log_time
    def search_torrent(self, search_term: str) -> None:
        if search_term:
            self.search_term = search_term
            self.search_active = True
            self._search_torrent(search_term, forward=True)

    @log_time
    def _reset_search(self) -> None:
        self.search_active = False
        self.search_idx = 0
        self.search_term = ""

    @log_time
    def on_key(self, event: events.Key) -> None:
        """Reset search status on any key press that are not search-related"""
        if self.search_active and event.key != "n" and event.key != "N":
            self._reset_search()
            self.post_message(SearchStateChangedEvent())

    # Handlers

    @log_time
    @on(TorrentRemovedEvent)
    def handle_torrent_removed_event(self, event: TorrentRemovedEvent) -> None:
        self._remove_item(event.torrent_hash)

    @log_time
    @on(TorrentTrashedEvent)
    def handle_torrent_trashed_event(self, event: TorrentRemovedEvent) -> None:
        self._remove_item(event.torrent_hash)

    @log_time
    def _remove_item(self, torrent_hash: str) -> None:
        """Remove torrent from page until next torrent list update."""
        self.page_torrents = [
            t for t in self.page_torrents if t.hash != torrent_hash
        ]

        self._item_cache.clear()
        self._update_virtual_size()
        self.index = self.validate_index(self.index)
        self.refresh()

    # Common helpers

    @log_time
    def torrent_idx(self, torrent) -> Optional[int]:
        return next(
            (
                idx
                for idx, t in enumerate(self.r_torrents)
                if t.hash == torrent.hash
            ),
            None,
        )

    @log_time
    def get_hl_torrent(self) -> Optional[Torrent]:
        if self.index is not None and self.index < len(self.page_torrents):
            return self.page_torrents[self.index]

    @log_time
    def get_hl_torrent_id(self) -> Optional[str]:
        if (hl_torrent := self.get_hl_torrent()) is not None:
            return hl_torrent.hash
