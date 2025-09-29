from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from rich.table import Table

from portfolio_tool.core.reports import LotRow, PositionRow


def _fmt_decimal(value: Decimal | None, fmt: str = "{:.2f}") -> str:
    if value is None:
        return "-"
    return fmt.format(value)


def positions_table(rows: Iterable[PositionRow]) -> Table:
    table = Table(title="Positions")
    table.add_column("Symbol")
    table.add_column("Qty")
    table.add_column("Avg Cost")
    table.add_column("Last Price")
    table.add_column("Market Value")
    table.add_column("Unrealised $")
    table.add_column("Unrealised %")
    table.add_column("Weight")
    for row in rows:
        table.add_row(
            row.symbol,
            _fmt_decimal(row.quantity, "{:.4f}"),
            _fmt_decimal(row.avg_cost),
            _fmt_decimal(row.price),
            _fmt_decimal(row.market_value),
            _fmt_decimal(row.unrealised_pl),
            _fmt_decimal(row.unrealised_pct, "{:.2%}"),
            _fmt_decimal(row.weight, "{:.2%}"),
        )
    return table


def lots_table(rows: Iterable[LotRow]) -> Table:
    table = Table(title="Lots")
    table.add_column("Lot ID")
    table.add_column("Symbol")
    table.add_column("Acquired")
    table.add_column("Qty")
    table.add_column("Cost Base")
    table.add_column("CGT Threshold")
    for row in rows:
        table.add_row(
            str(row.lot_id),
            row.symbol,
            row.acquired_at.isoformat(),
            _fmt_decimal(row.qty_remaining, "{:.4f}"),
            _fmt_decimal(row.cost_base),
            row.threshold_date.isoformat(),
        )
    return table


__all__ = ["positions_table", "lots_table"]
