from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from portfolio_tool.config import Config
from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.data import models


@dataclass
class PositionRow:
    symbol: str
    quantity: Decimal
    cost_base: Decimal
    avg_cost: Decimal
    price: Decimal | None
    currency: str | None
    market_value: Decimal | None
    unrealised_pl: Decimal | None
    unrealised_pct: Decimal | None
    weight: Decimal | None


@dataclass
class LotRow:
    lot_id: int
    symbol: str
    acquired_at: dt.datetime
    qty_remaining: Decimal
    cost_base: Decimal
    threshold_date: dt.date


def _quantize(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_positions(session: Session, cfg: Config, pricing: PriceService) -> list[PositionRow]:
    stmt = select(models.Lot).where(models.Lot.qty_remaining > 0)
    lots = list(session.scalars(stmt))
    aggregated: dict[str, dict[str, Decimal]] = {}
    for lot in lots:
        symbol = lot.symbol.upper()
        data = aggregated.setdefault(
            symbol,
            {
                "qty": Decimal("0"),
                "cost": Decimal("0"),
            },
        )
        data["qty"] += Decimal(lot.qty_remaining)
        data["cost"] += Decimal(lot.cost_base_total)
    quotes: dict[str, PriceQuote] = pricing.get_quotes(session, list(aggregated.keys())) if aggregated else {}
    total_value = Decimal("0")
    for symbol, data in aggregated.items():
        quote = quotes.get(symbol)
        if quote:
            total_value += Decimal(data["qty"]) * Decimal(quote.price)
    rows: list[PositionRow] = []
    for symbol, data in sorted(aggregated.items()):
        qty = data["qty"]
        cost = data["cost"]
        avg_cost = (cost / qty) if qty else Decimal("0")
        quote = quotes.get(symbol)
        if quote:
            price = quote.price
            currency = quote.currency
            market_value = qty * price
            unrealised_pl = market_value - cost
            unrealised_pct = (unrealised_pl / cost) if cost else None
            weight = (market_value / total_value) if total_value else None
        else:
            price = None
            currency = None
            market_value = None
            unrealised_pl = None
            unrealised_pct = None
            weight = None
        rows.append(
            PositionRow(
                symbol=symbol,
                quantity=qty,
                cost_base=cost,
                avg_cost=avg_cost,
                price=price,
                currency=currency,
                market_value=market_value,
                unrealised_pl=unrealised_pl,
                unrealised_pct=unrealised_pct,
                weight=weight,
            )
        )
    return rows


def build_lots(session: Session, symbol: str) -> list[LotRow]:
    stmt = select(models.Lot).where(models.Lot.symbol == symbol.upper()).order_by(models.Lot.acquired_at)
    rows: list[LotRow] = []
    for lot in session.scalars(stmt):
        rows.append(
            LotRow(
                lot_id=lot.id,
                symbol=lot.symbol,
                acquired_at=lot.acquired_at,
                qty_remaining=Decimal(lot.qty_remaining),
                cost_base=Decimal(lot.cost_base_total),
                threshold_date=lot.threshold_date,
            )
        )
    return rows


def build_cgt_calendar(session: Session, cfg: Config, window_days: int) -> list[LotRow]:
    horizon = dt.date.today() + dt.timedelta(days=window_days)
    stmt = select(models.Lot).where(
        models.Lot.qty_remaining > 0,
        models.Lot.threshold_date <= horizon,
    )
    lots = [
        LotRow(
            lot_id=lot.id,
            symbol=lot.symbol,
            acquired_at=lot.acquired_at,
            qty_remaining=Decimal(lot.qty_remaining),
            cost_base=Decimal(lot.cost_base_total),
            threshold_date=lot.threshold_date,
        )
        for lot in session.scalars(stmt)
    ]
    lots.sort(key=lambda r: r.threshold_date)
    return lots


def build_pnl(session: Session, realised: bool = True) -> list[dict]:
    if realised:
        stmt = select(models.Disposal)
        rows = []
        for disposal in session.scalars(stmt):
            rows.append(
                {
                    "symbol": disposal.lot.symbol,
                    "lot_id": disposal.lot_id,
                    "qty": Decimal(disposal.qty),
                    "gain_loss": Decimal(disposal.gain_loss),
                    "eligible_discount": disposal.eligible_discount,
                }
            )
        return rows
    else:
        stmt = select(models.Lot).where(models.Lot.qty_remaining > 0)
        rows = []
        for lot in session.scalars(stmt):
            rows.append(
                {
                    "symbol": lot.symbol,
                    "lot_id": lot.id,
                    "qty": Decimal(lot.qty_remaining),
                    "cost_base": Decimal(lot.cost_base_total),
                    "threshold_date": lot.threshold_date,
                }
            )
        return rows


def build_audit_log(session: Session) -> list[dict]:
    stmt = select(models.AuditLog).order_by(models.AuditLog.created_at)
    logs: list[dict] = []
    for entry in session.scalars(stmt):
        logs.append(
            {
                "id": entry.id,
                "action": entry.action,
                "entity": entry.entity,
                "entity_id": entry.entity_id,
                "created_at": entry.created_at,
                "payload": entry.payload,
            }
        )
    return logs


__all__ = [
    "build_positions",
    "build_lots",
    "build_cgt_calendar",
    "build_pnl",
    "build_audit_log",
    "PositionRow",
    "LotRow",
]
