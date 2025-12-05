"""Web search query input dialog."""

from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import Input, Static, SelectionList
from textual.widgets.selection_list import Selection
from textual.app import ComposeResult
from textual.screen import ModalScreen
from typing import ClassVar

from ...common import JackettCategories
from ...message import WebSearchQuerySubmitted, Notification
from ...util.decorator import log_time
from ...ui.widget.common import VimSelectionList


class WebSearchQueryDialog(ModalScreen[None]):
    """Modal dialog for entering web search query."""

    @log_time
    def __init__(self, initial_query: str = None):
        super().__init__()
        self.initial_query = initial_query

    @log_time
    def compose(self) -> ComposeResult:
        yield WebSearchQueryWidget(self.initial_query)


class WebSearchQueryWidget(Static):
    """Input widget for web search query."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "submit_query", "[Action] Search", priority=True),
        Binding("tab", "focus_next", "[Navigation] Next field"),
        Binding("escape", "close", "[Navigation] Cancel"),
    ]

    @log_time
    def __init__(self, initial_query: str = None):
        super().__init__()
        self.initial_query = initial_query

    @log_time
    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="Search for torrents...",
            id="websearch-query-input"
        )
        with Horizontal():
            yield VimSelectionList[str](
                *self._build_indexer_selections(),
                id="websearch-indexers-list"
            )
            yield VimSelectionList[str](
                *self._build_category_selections(),
                id="websearch-categories-list"
            )

    def _build_indexer_selections(self) -> list[Selection]:
        """Build selection list from all provider indexers.

        Returns:
            List of Selection objects with all indexers
        """
        selections = []
        for indexer in self.app.search.get_indexers():
            selections.append(
                Selection(indexer.name, indexer.id, True))
        return selections

    def _build_category_selections(self) -> list[Selection]:
        selections = []
        for category in JackettCategories.parent_categories():
            # Use category object as value instead of ID
            selections.append(
                Selection(category.full_path, category, True))
        return selections

    @log_time
    def on_mount(self) -> None:
        """Focus on input when dialog opens."""
        self.border_title = 'Search torrents'
        self.border_subtitle = ('(Enter) Search / (Tab) Switch / '
                                '(Space) Toggle selection / (ESC) Close')

        self.query_one("#websearch-indexers-list").border_title = "Search indexers"
        self.query_one("#websearch-categories-list").border_title = "Categories"

        input_widget = self.query_one("#websearch-query-input", Input)
        if self.initial_query:
            input_widget.value = self.initial_query
        input_widget.focus()

    @log_time
    def action_submit_query(self) -> None:
        """Submit search query and close dialog."""
        input_widget = self.query_one("#websearch-query-input", Input)
        query = input_widget.value.strip()

        if not query:
            self.post_message(Notification(
                "Please enter a search term",
                "warning"))
            return

        # Get selected indexers
        indexers_list = self.query_one(
            "#websearch-indexers-list", SelectionList)
        selected_indexers = list(indexers_list.selected)

        # Get selected categories (Category objects)
        categories_list = self.query_one(
            "#websearch-categories-list", SelectionList)
        selected_categories = list(categories_list.selected)

        if not selected_indexers:
            self.post_message(Notification(
                "Please select at least one indexer",
                "warning"))
            return

        if not selected_categories:
            self.post_message(Notification(
                "Please select at least one category",
                "warning"))
            return

        # If all categories are selected, pass None to search everything
        all_categories_count = len(JackettCategories.parent_categories())
        if len(selected_categories) == all_categories_count:
            selected_categories = None

        # Post message with query, selected indexers, selected Category objects
        self.post_message(WebSearchQuerySubmitted(query,
                                                  selected_indexers,
                                                  selected_categories))

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
