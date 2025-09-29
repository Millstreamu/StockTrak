from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Iterable

from portfolio_tool.core.reports import LotRow, PositionRow


def _fmt(value: Decimal | None, fmt: str = "{:.2f}") -> str:
    if value is None:
        return "-"
    return fmt.format(value)


def positions_markdown(rows: Iterable[PositionRow]) -> str:
    headers = [
        "Symbol",
        "Qty",
        "Avg Cost",
        "Last Price",
        "Market Value",
        "Unrealised $",
        "Unrealised %",
        "Weight",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + " --- |" * len(headers)]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.symbol,
                    _fmt(row.quantity, "{:.4f}"),
                    _fmt(row.avg_cost),
                    _fmt(row.price),
                    _fmt(row.market_value),
                    _fmt(row.unrealised_pl),
                    _fmt(row.unrealised_pct, "{:.2%}"),
                    _fmt(row.weight, "{:.2%}"),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def lots_markdown(rows: Iterable[LotRow]) -> str:
    headers = ["Lot ID", "Symbol", "Acquired", "Qty", "Cost Base", "CGT Threshold"]
    lines = ["| " + " | ".join(headers) + " |", "|" + " --- |" * len(headers)]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.lot_id),
                    row.symbol,
                    row.acquired_at.isoformat(),
                    _fmt(row.qty_remaining, "{:.4f}"),
                    _fmt(row.cost_base),
                    row.threshold_date.isoformat(),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


__all__ = ["positions_markdown", "lots_markdown"]
