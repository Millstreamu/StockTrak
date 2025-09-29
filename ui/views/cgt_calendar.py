from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Iterable

from textual.widgets import DataTable

from portfolio_tool.core.reports import LotRow

from .lots import LotSelected


class CGTCalendarView(DataTable):
    def __init__(self) -> None:
        super().__init__(cursor_type="row")
        self._rows: list[LotRow] = []

    def on_mount(self) -> None:
        self.add_column("Date", key="date", width=12)
        self.add_column("Symbol", key="symbol", width=10)
        self.add_column("Lot ID", key="lot_id", width=8)
        self.add_column("Qty", key="qty", width=12)
        for column in self.columns.values():
            if column.key not in {"symbol", "date"}:
                column.align = "right"
        self.show_header = True

    def update_rows(self, rows: Iterable[LotRow]) -> None:
        self._rows = list(rows)
        self.refresh_rows()

    def refresh_rows(self) -> None:
        self.clear()
        grouped: dict[dt.date, list[LotRow]] = defaultdict(list)
        for lot in self._rows:
            grouped[lot.threshold_date].append(lot)
        for threshold in sorted(grouped.keys()):
            for lot in grouped[threshold]:
                self.add_row(
                    threshold.isoformat(),
                    lot.symbol,
                    str(lot.lot_id),
                    f"{lot.qty_remaining:.4f}",
                    key=str(lot.lot_id),
                )
        if not grouped:
            self.add_row("—", "—", "—", "—")

    def on_row_selected(self, event: DataTable.RowSelected) -> None:  # type: ignore[override]
        if event.row_key and event.row_key != "—":
            self.post_message(LotSelected(int(event.row_key)))
