from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Optional

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from . import models

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.engine import Engine
else:  # pragma: no cover - fallback for stubbed SQLAlchemy
    Engine = Any


class Database:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self):
        models.Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def log_action(session: Session, action: str, entity: str, entity_id: int, payload: Optional[dict] = None):
    session.add(
        models.AuditLog(
            action=action,
            entity=entity,
            entity_id=entity_id,
            payload=json.dumps(payload, default=str) if payload else None,
        )
    )


def create_trade(session: Session, trade_data: dict, lots: list[dict] | None = None) -> models.Trade:
    trade = models.Trade(**trade_data)
    session.add(trade)
    session.flush()
    log_action(session, "create", "trade", trade.id, trade_data)
    if lots:
        for lot in lots:
            session.add(models.Lot(**lot))
    return trade


def update_trade(session: Session, trade_id: int, updates: dict) -> models.Trade:
    trade = session.get(models.Trade, trade_id)
    if not trade:
        raise ValueError("Trade not found")
    for key, value in updates.items():
        setattr(trade, key, value)
    log_action(session, "update", "trade", trade.id, updates)
    session.flush()
    return trade


def delete_trade(session: Session, trade_id: int) -> None:
    trade = session.get(models.Trade, trade_id)
    if not trade:
        raise ValueError("Trade not found")
    log_action(session, "delete", "trade", trade.id, {"side": trade.side, "symbol": trade.symbol})
    session.delete(trade)


def create_lot(
    session: Session,
    *,
    symbol: str,
    acquired_at: datetime,
    qty: Decimal,
    cost_base: Decimal,
    threshold_date,
    trade_id: int,
) -> models.Lot:
    lot = models.Lot(
        symbol=symbol,
        acquired_at=acquired_at,
        qty_remaining=qty,
        cost_base_total=cost_base,
        threshold_date=threshold_date,
        trade_id=trade_id,
    )
    session.add(lot)
    session.flush()
    return lot


def list_open_lots(session: Session, symbol: str) -> list[models.Lot]:
    stmt = select(models.Lot).where(models.Lot.symbol == symbol, models.Lot.qty_remaining > 0)
    return list(session.scalars(stmt))


def create_disposal(
    session: Session,
    *,
    sell_trade_id: int,
    lot_id: int,
    qty: Decimal,
    proceeds: Decimal,
    cost_base_alloc: Decimal,
    gain_loss: Decimal,
    eligible_discount: bool,
):
    disposal = models.Disposal(
        sell_trade_id=sell_trade_id,
        lot_id=lot_id,
        qty=qty,
        proceeds=proceeds,
        cost_base_alloc=cost_base_alloc,
        gain_loss=gain_loss,
        eligible_discount=eligible_discount,
    )
    session.add(disposal)
    return disposal


def upsert_price(
    session: Session,
    *,
    symbol: str,
    price: Decimal,
    currency: str,
    asof: datetime,
    provider: str,
    ttl_expires_at: datetime,
    is_stale: bool,
):
    stmt = select(models.PriceCache).where(models.PriceCache.symbol == symbol)
    existing = session.scalars(stmt).first()
    if existing:
        existing.price = price
        existing.currency = currency
        existing.asof = asof
        existing.provider = provider
        existing.ttl_expires_at = ttl_expires_at
        existing.is_stale = is_stale
        return existing
    price_obj = models.PriceCache(
        symbol=symbol,
        price=price,
        currency=currency,
        asof=asof,
        provider=provider,
        ttl_expires_at=ttl_expires_at,
        is_stale=is_stale,
    )
    session.add(price_obj)
    return price_obj


def get_price(session: Session, symbol: str) -> models.PriceCache | None:
    stmt = select(models.PriceCache).where(models.PriceCache.symbol == symbol)
    return session.scalars(stmt).first()


def list_positions(session: Session):
    stmt = select(models.Lot.symbol, func.sum(models.Lot.qty_remaining), func.sum(models.Lot.cost_base_total)).group_by(models.Lot.symbol)
    return session.execute(stmt).all()


def create_actionable(session: Session, **data):
    actionable = models.Actionable(**data)
    session.add(actionable)
    return actionable


def list_actionables(session: Session, status: str = "open") -> list[models.Actionable]:
    stmt = select(models.Actionable).where(models.Actionable.status == status)
    return list(session.scalars(stmt))


__all__ = [
    "Database",
    "create_trade",
    "update_trade",
    "delete_trade",
    "create_lot",
    "list_open_lots",
    "create_disposal",
    "upsert_price",
    "get_price",
    "list_positions",
    "create_actionable",
    "list_actionables",
    "log_action",
]
