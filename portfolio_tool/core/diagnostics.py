from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from portfolio_tool.config import Config
from portfolio_tool.core.pricing import PriceService
from portfolio_tool.data import models

PriceReason = Literal["no_prices", "stale", "offline_mode", "ok"]


@dataclass
class PriceSnapshot:
    symbol: str
    asof: Optional[dt.datetime]
    is_stale: bool


@dataclass
class PortfolioDiagnostics:
    db_path: Path
    db_exists: bool
    trade_count: int
    lot_count: int
    price_count: int
    actionable_count: int
    latest_price: PriceSnapshot | None
    offline_mode: bool
    price_provider: str
    price_ttl_minutes: int


def collect_diagnostics(cfg: Config, session: Session) -> PortfolioDiagnostics:
    def _count(model) -> int:
        stmt = select(model)
        return len(list(session.scalars(stmt)))

    trade_count = _count(models.Trade)
    lot_count = _count(models.Lot)
    price_count = _count(models.PriceCache)
    actionable_count = _count(models.Actionable)
    latest_row = (
        session.execute(
            select(models.PriceCache).order_by(models.PriceCache.asof.desc()).limit(1)
        )
        .scalars()
        .first()
    )
    latest_price = None
    if latest_row:
        latest_price = PriceSnapshot(
            symbol=latest_row.symbol,
            asof=PriceService._ensure_aware(latest_row.asof),
            is_stale=bool(getattr(latest_row, "is_stale", False)),
        )
    return PortfolioDiagnostics(
        db_path=cfg.db_path,
        db_exists=cfg.db_path.exists(),
        trade_count=int(trade_count),
        lot_count=int(lot_count),
        price_count=int(price_count),
        actionable_count=int(actionable_count),
        latest_price=latest_price,
        offline_mode=cfg.offline_mode,
        price_provider=cfg.price_provider,
        price_ttl_minutes=cfg.price_ttl_minutes,
    )


def determine_price_status(diagnostics: PortfolioDiagnostics) -> tuple[Optional[dt.datetime], PriceReason]:
    latest = diagnostics.latest_price
    if diagnostics.offline_mode:
        asof = latest.asof if latest else None
        return asof, "offline_mode"
    if diagnostics.price_count == 0 or latest is None:
        return None, "no_prices"
    if latest.is_stale:
        return latest.asof, "stale"
    return latest.asof, "ok"


__all__ = [
    "PriceReason",
    "PriceSnapshot",
    "PortfolioDiagnostics",
    "collect_diagnostics",
    "determine_price_status",
]
