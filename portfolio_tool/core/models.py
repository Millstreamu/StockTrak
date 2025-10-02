"""Domain models for the portfolio tool."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _ensure_aware(name: str, value: datetime | None) -> datetime | None:
    """Ensure that datetimes stored on models are timezone-aware."""

    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(slots=True)
class Instrument:
    symbol: str
    name: str
    exchange: str
    currency: str


@dataclass(slots=True)
class Transaction:
    dt: datetime = field(metadata={"tz": True})
    type: str = field(metadata={"enum": {"BUY", "SELL", "DRP", "SPLIT"}})
    symbol: str
    qty: float
    price: float
    fees: float = 0.0
    broker_ref: Optional[str] = None
    notes: Optional[str] = None
    exchange: Optional[str] = None
    id: Optional[int] = None

    def __post_init__(self) -> None:
        _ensure_aware("Transaction.dt", self.dt)
        self.type = self.type.upper()


@dataclass(slots=True)
class Lot:
    symbol: str
    acquired_at: datetime
    qty_remaining: float
    cost_base_total: float
    threshold_date: Optional[datetime]
    lot_id: Optional[int] = None
    source_txn_id: Optional[int] = None

    def __post_init__(self) -> None:
        _ensure_aware("Lot.acquired_at", self.acquired_at)
        _ensure_aware("Lot.threshold_date", self.threshold_date)


@dataclass(slots=True)
class Disposal:
    sell_txn_id: Optional[int]
    lot_id: Optional[int]
    qty: float
    proceeds: float
    cost_base_alloc: float
    gain_loss: float
    eligible_for_discount: bool
    id: Optional[int] = None


@dataclass(slots=True)
class Position:
    symbol: str
    total_qty: float
    avg_cost: float
    mv: Optional[float]
    weight: Optional[float]


@dataclass(slots=True)
class Actionable:
    type: str
    message: str
    status: str
    created_at: datetime
    updated_at: datetime
    symbol: Optional[str] = None
    snoozed_until: Optional[datetime] = None
    context: Optional[str] = None
    id: Optional[int] = None

    def __post_init__(self) -> None:
        _ensure_aware("Actionable.created_at", self.created_at)
        _ensure_aware("Actionable.updated_at", self.updated_at)
        _ensure_aware("Actionable.snoozed_until", self.snoozed_until)


@dataclass(slots=True)
class PriceQuote:
    symbol: str
    asof: datetime
    price: float
    source: str
    stale: bool

    def __post_init__(self) -> None:
        _ensure_aware("PriceQuote.asof", self.asof)


__all__ = [
    "Instrument",
    "Transaction",
    "Lot",
    "Disposal",
    "Position",
    "Actionable",
    "PriceQuote",
]
