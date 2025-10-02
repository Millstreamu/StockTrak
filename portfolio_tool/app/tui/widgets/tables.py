"""Reusable paged table widget for the TUI."""
from __future__ import annotations

from typing import Callable, Sequence

from .._textual import DataTable

Loader = Callable[[int, int, str], tuple[Sequence[dict[str, object]], int]]


class PagedTable(DataTable):
    """DataTable with simple pagination support."""

    def __init__(
        self,
        *,
        columns: Sequence[tuple[str, str]],
        key_field: str = "id",
        page_size: int = 20,
    ) -> None:
        super().__init__(zebra_stripes=True)
        self._columns = list(columns)
        self._key_field = key_field
        self._page_size = max(page_size, 1)
        self._loader: Loader | None = None
        self._page = 0
        self._total = 0
        self._filter = ""
        self._row_cache: dict[str, dict[str, object]] = {}

    # ------------------------------------------------------------------
    def _setup_columns(self) -> None:
        for key, title in self._columns:
            self.add_column(title, key=key)

    def on_mount(self) -> None:
        if not self.columns:
            self.clear()
            self._setup_columns()

    # ------------------------------------------------------------------
    def set_loader(self, loader: Loader) -> None:
        self._loader = loader

    # ------------------------------------------------------------------
    def set_filter(self, text: str) -> None:
        self._filter = text.strip().upper()
        self._page = 0
        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        if not self._loader:
            return
        rows, total = self._loader(self._page, self._page_size, self._filter)
        self._total = int(total)
        self._row_cache.clear()
        self.clear(columns=True)
        self._setup_columns()
        for idx, row in enumerate(rows):
            key_value = row.get(self._key_field, f"row-{self._page}-{idx}")
            row_key = str(key_value)
            values: list[str] = []
            for key, _ in self._columns:
                value = row.get(key)
                if value is None:
                    values.append("")
                elif isinstance(value, float):
                    values.append(f"{value:,.2f}")
                else:
                    values.append(str(value))
            self.add_row(*values, key=row_key)
            self._row_cache[row_key] = dict(row)
        if self.row_count:
            try:
                self.cursor_type = "row"
                self.move_cursor(row=0, column=0)
            except Exception:  # pragma: no cover - best effort
                pass

    # ------------------------------------------------------------------
    def get_selected_row(self) -> dict[str, object] | None:
        row_key = self.cursor_row
        if row_key is None:
            return None
        return self._row_cache.get(str(row_key))

    # ------------------------------------------------------------------
    def page_info(self) -> str:
        if not self._loader:
            return ""
        start = self._page * self._page_size + 1 if self.row_count else 0
        end = self._page * self._page_size + self.row_count
        return f"{start}-{end} of {self._total}"

    # ------------------------------------------------------------------
    def next_page(self) -> None:
        if (self._page + 1) * self._page_size >= max(self._total, self.row_count):
            return
        self._page += 1
        self.reload()

    # ------------------------------------------------------------------
    def previous_page(self) -> None:
        if self._page == 0:
            return
        self._page -= 1
        self.reload()


__all__ = ["PagedTable", "Loader"]
