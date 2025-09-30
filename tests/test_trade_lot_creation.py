from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import create_engine, select
from zoneinfo import ZoneInfo

from portfolio_tool.config import Config
from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models
from portfolio_tool.data.repo import Database


def test_buy_creates_lot_immediately() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = Database(engine)
    cfg = Config()

    trade_input = TradeInput(
        side="BUY",
        symbol="XYZ",
        dt=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
        qty=Decimal("100"),
        price=Decimal("10"),
        fees=Decimal("5"),
        exchange="ASX",
        note="Test",
    )

    with db.session_scope() as session:
        record_trade(session, cfg, trade_input)

    with db.session_scope() as session:
        lots = list(session.scalars(select(models.Lot)))
        assert len(lots) == 1
        lot = lots[0]
        assert lot.qty_remaining == trade_input.qty
        expected_cost_base = trade_input.qty * trade_input.price + trade_input.fees
        assert lot.cost_base_total == expected_cost_base
        tz = ZoneInfo(cfg.timezone)
        expected_threshold = trade_input.dt.astimezone(tz).date() + dt.timedelta(days=365)
        assert lot.threshold_date == expected_threshold
