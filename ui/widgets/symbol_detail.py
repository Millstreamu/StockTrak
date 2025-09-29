from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.table import Table
from textual.widget import Widget


class SymbolDetailWidget(Widget):
    def __init__(self) -> None:
        super().__init__(id="symbol-detail")
        self._detail: dict[str, Any] | None = None
        self.display = False

    def update_detail(self, detail: dict[str, Any] | None) -> None:
        self._detail = detail
        self.display = detail is not None
        self.refresh()

    def render(self) -> Panel:
        if not self._detail:
            return Panel("Select a position", title="Symbol Detail")
        symbol = self._detail.get("symbol", "")
        lots = self._detail.get("lots", [])
        trades = self._detail.get("trades", [])
        price = self._detail.get("price")
        table = Table.grid(padding=(0, 1))
        info = Table.grid(padding=0)
        info.add_row(f"Symbol: [bold]{symbol}[/bold]")
        if price:
            info.add_row(f"Last Price: {price.price} {price.currency}")
            info.add_row(f"As of: {price.asof}")
        table.add_row(Panel(info, title="Snapshot"))
        lots_table = Table(title="Lots", expand=True)
        lots_table.add_column("Lot")
        lots_table.add_column("Qty")
        lots_table.add_column("Cost")
        lots_table.add_column("Threshold")
        for lot in lots:
            lots_table.add_row(
                str(lot.lot_id),
                f"{lot.qty_remaining:.4f}",
                f"{lot.cost_base:.2f}",
                lot.threshold_date.isoformat(),
            )
        if not lots:
            lots_table.add_row("—", "—", "—", "—")
        table.add_row(lots_table)
        trades_table = Table(title="Recent Trades", expand=True)
        trades_table.add_column("ID")
        trades_table.add_column("Side")
        trades_table.add_column("Qty")
        trades_table.add_column("Price")
        trades_table.add_column("Date")
        for trade in trades:
            trades_table.add_row(
                str(trade.id),
                trade.side,
                f"{trade.qty:.4f}",
                f"{trade.price:.2f}",
                trade.dt.isoformat(),
            )
        if not trades:
            trades_table.add_row("—", "—", "—", "—", "—")
        table.add_row(trades_table)
        return Panel(table, title=f"{symbol} Detail")
