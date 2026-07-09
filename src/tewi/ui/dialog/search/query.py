"""Web search query input dialog."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, SelectionList, Static
from textual.widgets.selection_list import Selection

from ....search.models import SearchPreset, StandardCategories
from ....util.log import log_time
from ...messages import Notification, WebSearchQuerySubmitted
from ...util import subtitle_keys
from ...widget.common import CycleSelect, VimSelectionList


class WebSearchQueryDialog(ModalScreen[None]):
    """Modal dialog for entering web search query."""

    @log_time
    def __init__(
        self,
        initial_query: str = None,
        initial_indexers: list[str] | None = None,
        initial_categories: list | None = None,
        presets: list[SearchPreset] | None = None,
        default_preset: str | None = None,
        restore_preset: str | None = None,
    ):
        super().__init__()
        self.initial_query = initial_query
        self.initial_indexers = initial_indexers
        self.initial_categories = initial_categories
        self.presets = presets or []
        self.default_preset = default_preset
        self.restore_preset = restore_preset

    @log_time
    def compose(self) -> ComposeResult:
        yield WebSearchQueryWidget(
            self.initial_query,
            self.initial_indexers,
            self.initial_categories,
            self.presets,
            self.default_preset,
            self.restore_preset,
        )


class WebSearchQueryWidget(Static):
    """Input widget for web search query."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "submit_query", "[Action] Search", priority=True),
        Binding("tab", "focus_next", "[Navigation] Next field"),
        Binding("escape", "close", "[Navigation] Cancel"),
    ]

    @log_time
    def __init__(
        self,
        initial_query: str = None,
        initial_indexers: list[str] | None = None,
        initial_categories: list | None = None,
        presets: list[SearchPreset] | None = None,
        default_preset: str | None = None,
        restore_preset: str | None = None,
    ):
        super().__init__()
        self.initial_query = initial_query
        self.initial_indexers = initial_indexers
        self.initial_categories = initial_categories
        self._presets = presets or []
        self._default_preset = default_preset
        self._restore_preset = restore_preset
        self._skip_preset_apply = False
        self._indexer_order: list[str] = []
        self._category_order: list = []
        self._indexer_name_to_id: dict[str, str] = {}

    @log_time
    def compose(self) -> ComposeResult:
        with Horizontal(id="websearch-query-row"):
            yield Input(
                placeholder="Type search query...",
                id="websearch-query-input",
            )
            if self._presets:
                options = [("Default", None)] + [
                    (p.name, p) for p in self._presets
                ]
                yield CycleSelect(options, id="websearch-preset-cycle")
        with Horizontal():
            yield VimSelectionList[str](
                *self._build_indexer_selections(),
                id="websearch-indexers-list",
            )
            yield VimSelectionList[str](
                *self._build_category_selections(),
                id="websearch-categories-list",
            )

    def _build_indexer_selections(self) -> list[Selection]:
        """Build selection list from all provider indexers.

        Returns:
            List of Selection objects with all indexers
        """
        selections = []
        available_indexers = self.app.search.get_indexers()
        available_indexer_ids = {idx.id for idx in available_indexers}

        # Determine which indexers should be selected
        if self.initial_indexers is not None:
            # Filter to only include indexers that still exist
            selected_ids = set(
                idx
                for idx in self.initial_indexers
                if idx in available_indexer_ids
            )
        else:
            # Default: all indexers selected
            selected_ids = available_indexer_ids

        self._indexer_order = []
        self._indexer_name_to_id = {}
        for indexer in available_indexers:
            is_selected = indexer.id in selected_ids
            self._indexer_order.append(indexer.id)
            selections.append(
                Selection(
                    indexer.display_name or indexer.name,
                    indexer.id,
                    is_selected,
                )
            )
            self._indexer_name_to_id[indexer.name.lower()] = indexer.id
        return selections

    def _build_category_selections(self) -> list[Selection]:
        """Build selection list from all standard categories."""
        selections = []
        all_categories = StandardCategories.parent_categories()

        # Determine which categories should be selected
        if self.initial_categories is not None:
            # Create set of category full_paths from initial categories
            selected_paths = {cat.full_path for cat in self.initial_categories}
        else:
            # Default: all categories selected
            selected_paths = {cat.full_path for cat in all_categories}

        self._category_order = []
        for category in all_categories:
            is_selected = category.full_path in selected_paths
            self._category_order.append(category)
            selections.append(
                # Use category object as value instead of ID
                Selection(category.full_path, category, is_selected)
            )
        return selections

    def _resolve_indexer_id(self, preset_id: str) -> str | None:
        """Resolve preset indexer ID, supporting name-based Prowlarr IDs.

        Allows presets to reference Prowlarr indexers by name
        (e.g. ``prowlarr:1337x``) in addition to numeric ID
        (e.g. ``prowlarr:12``). Returns the canonical indexer ID,
        or None if a name-based reference cannot be resolved.
        """
        if preset_id.startswith("prowlarr:"):
            suffix = preset_id.removeprefix("prowlarr:")
            if not suffix.isdigit() and suffix != "all":
                return self._indexer_name_to_id.get(suffix.lower())
        return preset_id

    @log_time
    def on_mount(self) -> None:
        """Focus on input when dialog opens."""
        self.border_title = "Search torrents"
        self.border_subtitle = subtitle_keys(
            ("Enter", "Search"),
            ("Tab", "Switch"),
            ("Space", "Toggle selection"),
            ("ESC", "Close"),
        )

        self.query_one("#websearch-indexers-list").border_title = "Indexers"
        self.query_one("#websearch-categories-list").border_title = "Categories"

        if self._presets:
            cycle = self.query_one("#websearch-preset-cycle", CycleSelect)
            cycle.border_title = "Preset"
            names = [p.name for p in self._presets]
            if self._default_preset and self._default_preset in names:
                cycle.index = names.index(self._default_preset) + 1
            elif self._restore_preset and self._restore_preset in names:
                self._skip_preset_apply = True
                cycle.index = names.index(self._restore_preset) + 1

        input_widget = self.query_one("#websearch-query-input", Input)
        if self.initial_query:
            input_widget.value = self.initial_query
        input_widget.focus()

    @log_time
    @on(CycleSelect.Changed, "#websearch-preset-cycle")
    def handle_preset_changed(self, event: CycleSelect.Changed) -> None:
        """Apply preset to indexer and category selections."""
        if self._skip_preset_apply:
            self._skip_preset_apply = False
            return
        self._apply_preset(event.value)

    def _apply_preset(self, preset: SearchPreset | None) -> None:
        """Apply a preset's indexers and categories to the selection lists."""
        indexers_list = self.query_one(
            "#websearch-indexers-list", SelectionList
        )
        categories_list = self.query_one(
            "#websearch-categories-list", SelectionList
        )

        if preset is None or preset.indexers is None:
            indexers_list.select_all()
        else:
            indexers_list.deselect_all()
            preset_ids = set()
            for pid in preset.indexers:
                resolved = self._resolve_indexer_id(pid)
                if resolved:
                    preset_ids.add(resolved)
            for indexer_id in self._indexer_order:
                if indexer_id in preset_ids:
                    indexers_list.select(indexer_id)

        if preset is None or preset.categories is None:
            categories_list.select_all()
        else:
            categories_list.deselect_all()
            preset_paths = set(preset.categories)
            for category in self._category_order:
                if category.full_path in preset_paths:
                    categories_list.select(category)

    @log_time
    def action_submit_query(self) -> None:
        """Submit search query and close dialog."""
        input_widget = self.query_one("#websearch-query-input", Input)
        query = input_widget.value.strip()

        if not query:
            self.post_message(
                Notification("Please enter a search term", "warning")
            )
            return

        # Get selected indexers
        indexers_list = self.query_one(
            "#websearch-indexers-list", SelectionList
        )
        selected_indexers = list(indexers_list.selected)

        # Get selected categories (Category objects)
        categories_list = self.query_one(
            "#websearch-categories-list", SelectionList
        )
        selected_categories = list(categories_list.selected)

        if not selected_indexers:
            self.post_message(
                Notification("Please select at least one indexer", "warning")
            )
            return

        if not selected_categories:
            self.post_message(
                Notification("Please select at least one category", "warning")
            )
            return

        # If all categories are selected, pass None to search everything
        all_categories_count = len(StandardCategories.parent_categories())
        if len(selected_categories) == all_categories_count:
            selected_categories = None

        selected_preset = None
        if self._presets:
            cycle = self.query_one("#websearch-preset-cycle", CycleSelect)
            preset = cycle.value
            selected_preset = preset.name if preset else None

        # Post message with query, selected indexers, selected Category objects
        self.post_message(
            WebSearchQuerySubmitted(
                query, selected_indexers, selected_categories, selected_preset
            )
        )

        # Close dialog
        self.parent.dismiss()

    @log_time
    def action_focus_next(self) -> None:
        """Focus next widget (Tab navigation)."""
        self.screen.focus_next()

    @log_time
    def action_close(self) -> None:
        """Close dialog without searching."""
        self.parent.dismiss()
