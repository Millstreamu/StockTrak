from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models


def _buy_trade(dt_value: dt.datetime, fees: str, cfg, session):
    record_trade(
        session,
        cfg,
        TradeInput(
            side="BUY",
            symbol="XYZ",
            dt=dt_value,
            qty=Decimal("10"),
            price=Decimal("10"),
            fees=Decimal(fees),
        ),
    )


def _sell_trade(dt_value: dt.datetime, fees: str, cfg, session):
    record_trade(
        session,
        cfg,
        TradeInput(
            side="SELL",
            symbol="XYZ",
            dt=dt_value,
            qty=Decimal("10"),
            price=Decimal("12"),
            fees=Decimal(fees),
        ),
    )


def test_buy_allocation_increases_cost_base(cfg, db):
    cfg.brokerage_allocation = "BUY"
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        _buy_trade(base_dt, "10", cfg, session)
        lot = session.scalars(select(models.Lot)).one()
        assert Decimal(lot.cost_base_total) == Decimal("110")


def test_sell_allocation_reduces_proceeds(cfg, db):
    cfg.brokerage_allocation = "SELL"
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        _buy_trade(base_dt, "0", cfg, session)
        _sell_trade(base_dt + dt.timedelta(days=2), "10", cfg, session)
        disposal = session.scalars(select(models.Disposal)).one()
        assert Decimal(disposal.proceeds) == Decimal("110")


def test_split_allocation_shares_fees(cfg, db):
    cfg.brokerage_allocation = "SPLIT"
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        _buy_trade(base_dt, "10", cfg, session)
        lot = session.scalars(select(models.Lot)).one()
        assert Decimal(lot.cost_base_total) == Decimal("105")
        _sell_trade(base_dt + dt.timedelta(days=2), "10", cfg, session)
        disposal = session.scalars(select(models.Disposal)).one()
        assert Decimal(disposal.proceeds) == Decimal("115")
