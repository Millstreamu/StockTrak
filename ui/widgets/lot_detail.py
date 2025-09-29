from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.table import Table
from textual.widget import Widget


class LotDetailWidget(Widget):
    def __init__(self) -> None:
        super().__init__(id="lot-detail")
        self._detail: dict[str, Any] | None = None
        self.display = False

    def update_detail(self, detail: dict[str, Any] | None) -> None:
        self._detail = detail
        self.display = detail is not None
        self.refresh()

    def render(self) -> Panel:
        if not self._detail:
            return Panel("Select a lot", title="Lot Detail")
        lot = self._detail.get("lot")
        trade = self._detail.get("trade")
        table = Table.grid(padding=1)
        table.add_row(f"Lot ID: [bold]{lot.id}[/bold]")
        table.add_row(f"Symbol: {lot.symbol}")
        table.add_row(f"Acquired: {lot.acquired_at}")
        table.add_row(f"Threshold: {lot.threshold_date}")
        table.add_row(f"Qty Remaining: {lot.qty_remaining}")
        table.add_row(f"Cost Base: {lot.cost_base_total}")
        if trade:
            table.add_row(f"Trade ID: {trade.id}")
        return Panel(table, title="Lot Detail")
