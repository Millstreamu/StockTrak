from __future__ import annotations

import datetime as dt
from typing import Iterable, Optional

from textual.message import Message
from textual.widgets import DataTable

from portfolio_tool.core.reports import LotRow


class LotSelected(Message):
    def __init__(self, lot_id: int) -> None:
        self.lot_id = lot_id
        super().__init__()


class LotsView(DataTable):
    def __init__(self) -> None:
        super().__init__(cursor_type="row")
        self._all_rows: list[LotRow] = []
        self._filter_symbol: Optional[str] = None

    def on_mount(self) -> None:
        self.add_column("Lot ID", key="lot_id", width=8)
        self.add_column("Symbol", key="symbol", width=10)
        self.add_column("Acquired", key="acquired", width=16)
        self.add_column("Qty Remaining", key="qty", width=16)
        self.add_column("Cost Base", key="cost", width=12)
        self.add_column("Threshold", key="threshold", width=12)
        self.add_column("Eligible?", key="eligible", width=10)
        for column in self.columns.values():
            if column.key not in {"symbol"}:
                column.align = "right"
            column.allow_sort = True
        self.show_header = True

    def update_rows(self, rows: Iterable[LotRow]) -> None:
        self._all_rows = list(rows)
        self.refresh_rows()

    def refresh_rows(self) -> None:
        self.clear()
        for row in self._filtered_rows():
            self.add_row(
                str(row.lot_id),
                row.symbol,
                row.acquired_at.isoformat(),
                f"{row.qty_remaining:.4f}",
                f"{row.cost_base:.2f}",
                row.threshold_date.isoformat(),
                "Yes" if row.threshold_date <= dt.date.today() else "No",
                key=str(row.lot_id),
            )

    def _filtered_rows(self) -> Iterable[LotRow]:
        if self._filter_symbol:
            return [r for r in self._all_rows if r.symbol.upper() == self._filter_symbol]
        return self._all_rows

    def set_symbol_filter(self, symbol: Optional[str]) -> None:
        self._filter_symbol = symbol.upper() if symbol else None
        self.refresh_rows()

    def on_row_selected(self, event: DataTable.RowSelected) -> None:  # type: ignore[override]
        if event.row_key:
            self.post_message(LotSelected(int(event.row_key)))
