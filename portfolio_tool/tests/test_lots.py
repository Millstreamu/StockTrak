from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models


def _trade(dt_value: dt.datetime, qty: str, price: str, side: str = "BUY") -> TradeInput:
    return TradeInput(
        side=side,
        symbol="ABC",
        dt=dt_value,
        qty=Decimal(qty),
        price=Decimal(price),
        fees=Decimal("0"),
    )


def test_fifo_matching(cfg, db):
    cfg.lot_matching = "FIFO"
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        record_trade(session, cfg, _trade(base_dt, "10", "10"))
        record_trade(session, cfg, _trade(base_dt + dt.timedelta(days=1), "10", "12"))
        lot_ids = [
            lot.id
            for lot in session.scalars(select(models.Lot).order_by(models.Lot.acquired_at))
        ]
        record_trade(
            session,
            cfg,
            TradeInput(
                side="SELL",
                symbol="ABC",
                dt=base_dt + dt.timedelta(days=2),
                qty=Decimal("15"),
                price=Decimal("20"),
                fees=Decimal("0"),
            ),
            match_method="FIFO",
        )
        disposals = list(session.scalars(select(models.Disposal).order_by(models.Disposal.id)))
        assert [d.lot_id for d in disposals] == lot_ids
        assert [Decimal(d.qty) for d in disposals] == [Decimal("10"), Decimal("5")]


def test_hifo_matching(cfg, db):
    cfg.lot_matching = "HIFO"
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        record_trade(session, cfg, _trade(base_dt, "10", "10"))
        record_trade(session, cfg, _trade(base_dt + dt.timedelta(days=1), "10", "12"))
        lots = list(session.scalars(select(models.Lot).order_by(models.Lot.acquired_at)))
        high_cost_lot = lots[1]
        record_trade(
            session,
            cfg,
            TradeInput(
                side="SELL",
                symbol="ABC",
                dt=base_dt + dt.timedelta(days=2),
                qty=Decimal("5"),
                price=Decimal("20"),
                fees=Decimal("0"),
            ),
            match_method="HIFO",
        )
        disposal = session.scalars(select(models.Disposal)).one()
        assert disposal.lot_id == high_cost_lot.id


def test_specific_id_matching(cfg, db):
    cfg.lot_matching = "SPECIFIC_ID"
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        record_trade(session, cfg, _trade(base_dt, "10", "10"))
        record_trade(session, cfg, _trade(base_dt + dt.timedelta(days=1), "10", "12"))
        lots = list(session.scalars(select(models.Lot).order_by(models.Lot.acquired_at)))
        target_lot = lots[0]
        record_trade(
            session,
            cfg,
            TradeInput(
                side="SELL",
                symbol="ABC",
                dt=base_dt + dt.timedelta(days=2),
                qty=Decimal("5"),
                price=Decimal("20"),
                fees=Decimal("0"),
            ),
            match_method="SPECIFIC_ID",
            specific_ids=[target_lot.id],
        )
        disposal = session.scalars(select(models.Disposal)).one()
        assert disposal.lot_id == target_lot.id
