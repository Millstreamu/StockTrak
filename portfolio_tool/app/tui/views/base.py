"""Base view components for the Textual TUI."""
from __future__ import annotations

from typing import Sequence

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Input, Static

from ..widgets.tables import Loader, PagedTable


class PortfolioView(Vertical):
    """Base class for all portfolio views."""

    @property
    def services(self):  # pragma: no cover - simple delegation
        from ..app import PortfolioApp

        app = self.app
        if isinstance(app, PortfolioApp):
            return app.services
        return None

    def refresh_view(self) -> None:  # pragma: no cover - default no-op
        """Refresh the view's data."""

    def focus_search(self) -> None:  # pragma: no cover - default no-op
        """Focus the search control if available."""

    def handle_add(self) -> None:  # pragma: no cover - default no-op
        """Handle Add action for the current view."""

    def handle_edit(self) -> None:  # pragma: no cover - default no-op
        """Handle Edit action for the current view."""

    def handle_delete(self) -> None:  # pragma: no cover - default no-op
        """Handle Delete action for the current view."""

    def handle_save(self) -> None:  # pragma: no cover - default no-op
        """Handle Save/Export action for the current view."""

    def handle_refresh(self) -> None:  # pragma: no cover - default no-op
        """Handle refresh action for the current view."""


class TableView(PortfolioView):
    """Helper view that displays a paged table with search/filter."""

    search_query = reactive("")

    def __init__(
        self,
        *,
        title: str,
        columns: Sequence[tuple[str, str]],
        key_field: str = "id",
        page_size: int = 20,
    ) -> None:
        super().__init__(id=f"view-{title.lower().replace(' ', '-')}")
        self._title = title
        self._table = PagedTable(columns=columns, key_field=key_field, page_size=page_size)
        self._status = Static("", classes="table-status")
        self._search = Input(placeholder="Search…", id=f"{self.id}-search")
        self._loader: Loader | None = None

    @property
    def table(self) -> PagedTable:
        return self._table

    @property
    def status_label(self) -> Static:
        return self._status

    def compose(self) -> ComposeResult:
        yield Static(self._title, classes="view-title")
        with Horizontal(classes="search-row"):
            yield self._search
            yield self._status
        yield self._table

    def set_loader(self, loader: Loader) -> None:
        self._loader = loader
        self._table.set_loader(self._load_rows)

    def _load_rows(self, page: int, size: int, query: str):
        if not self._loader:
            return [], 0
        return self._loader(page, size, query)

    def refresh_view(self) -> None:
        self._table.reload()
        self._status.update(self.status_text())

    def handle_refresh(self) -> None:
        self.refresh_view()

    def focus_search(self) -> None:
        self._search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input is self._search:
            self.search_query = event.value
            self._table.set_filter(self.search_query)
            self._status.update(self.status_text())

    def on_mount(self) -> None:
        self._table.reload()
        self._status.update(self.status_text())

    def status_text(self) -> str:
        return self._table.page_info()


__all__ = ["PortfolioView", "TableView"]
