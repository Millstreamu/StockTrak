from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DataTable

from portfolio_tool.core.reports import PositionRow


class PositionSelected(Message):
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__()


class PositionsView(DataTable):
    """Table view for open positions."""

    def __init__(self) -> None:
        super().__init__(cursor_type="row")
        self.add_class("view")
        self._rows: list[PositionRow] = []
        self._filter: str | None = None

    def on_mount(self) -> None:
        self.add_column("Symbol", key="symbol")
        self.add_column("Quantity", key="quantity", width=12)
        self.add_column("Avg Cost", key="avg_cost", width=12)
        self.add_column("Last Price", key="price", width=12)
        self.add_column("Market Value", key="market_value", width=14)
        self.add_column("Unrealised $", key="unrealised_pl", width=14)
        self.add_column("Unrealised %", key="unrealised_pct", width=12)
        self.add_column("Weight %", key="weight", width=10)
        for column in self.columns.values():
            column.allow_sort = True
            if column.key not in {"symbol"}:
                column.align = "right"
        self.show_header = True
        self.show_cursor = True

    def update_rows(self, rows: Iterable[PositionRow]) -> None:
        self._rows = list(rows)
        self.refresh_rows()

    def refresh_rows(self) -> None:
        self.clear()
        for row in self._iter_rows():
            self.add_row(
                row.symbol,
                self._fmt_qty(row.quantity),
                self._fmt_money(row.avg_cost),
                self._fmt_money(row.price),
                self._fmt_money(row.market_value),
                self._fmt_money(row.unrealised_pl),
                self._fmt_pct(row.unrealised_pct),
                self._fmt_pct(row.weight),
                key=row.symbol,
            )
        if self._rows:
            self.focus()

    def _iter_rows(self) -> Iterable[PositionRow]:
        if self._filter:
            return [r for r in self._rows if r.symbol == self._filter]
        return self._rows

    def set_symbol_filter(self, symbol: str | None) -> None:
        self._filter = symbol.upper() if symbol else None
        self.refresh_rows()

    def _fmt_money(self, value: Decimal | None) -> str:
        if value is None:
            return "—"
        return f"{value:.2f}"

    def _fmt_pct(self, value: Decimal | None) -> str:
        if value is None:
            return "—"
        return f"{value * Decimal(100):.2f}%"

    def _fmt_qty(self, value: Decimal | None) -> str:
        if value is None:
            return "—"
        return f"{value:.4f}"

    def on_row_selected(self, event: DataTable.RowSelected) -> None:  # type: ignore[override]
        if event.row_key:
            self.post_message(PositionSelected(str(event.row_key)))

    def watch_cursor_row(self, value: int) -> None:  # pragma: no cover - Textual callback
        row_key = self.get_row_key(value)
        if row_key is not None:
            self.post_message(PositionSelected(str(row_key)))
