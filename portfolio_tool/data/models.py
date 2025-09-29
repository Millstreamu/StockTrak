from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    dt: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False, default=Decimal("0"))
    exchange: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        onupdate=lambda: dt.datetime.now(dt.timezone.utc),
    )

    disposals: Mapped[list["Disposal"]] = relationship(
        "Disposal", back_populates="sell_trade", cascade="all, delete-orphan"
    )
    lots: Mapped[list["Lot"]] = relationship(
        "Lot", back_populates="trade", cascade="all, delete-orphan"
    )


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    acquired_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    cost_base_total: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    threshold_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), nullable=False)

    trade: Mapped[Trade] = relationship("Trade", back_populates="lots")
    disposals: Mapped[list["Disposal"]] = relationship(
        "Disposal", back_populates="lot", cascade="all, delete-orphan"
    )


class Disposal(Base):
    __tablename__ = "disposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sell_trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), nullable=False)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    proceeds: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    cost_base_alloc: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    gain_loss: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    eligible_discount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    sell_trade: Mapped[Trade] = relationship("Trade", back_populates="disposals")
    lot: Mapped[Lot] = relationship("Lot", back_populates="disposals")


class PriceCache(Base):
    __tablename__ = "price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asof: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ttl_expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Actionable(Base):
    __tablename__ = "actionables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="open")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    context: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

