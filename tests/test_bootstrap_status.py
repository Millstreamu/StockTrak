from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from typer.testing import CliRunner
from sqlalchemy import select

from portfolio_tool.__main__ import app
from portfolio_tool.config import load_config
from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models
from portfolio_tool.data.init_db import ensure_db
from portfolio_tool.data.repo import Database


def test_bootstrap_status(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    engine = ensure_db()
    tables = {
        getattr(model, "__tablename__", model.__name__.lower())
        for model in engine.store.keys()
    }
    for expected in {"trades", "lots", "price_cache", "actionables"}:
        assert expected in tables

    cfg = load_config()
    db = Database(engine)

    trade_input = TradeInput(
        side="BUY",
        symbol="CSL.AX",
        dt=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
        qty=Decimal("1"),
        price=Decimal("100"),
        fees=Decimal("0"),
    )

    with db.session_scope() as session:
        record_trade(session, cfg, trade_input)

    with db.session_scope() as session:
        lots = list(session.scalars(select(models.Lot)))
        assert len(lots) == 1

    monkeypatch.setattr("portfolio_tool.__main__.ensure_db", lambda: engine)

    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    trades_match = re.search(r"Trades\s+[^0-9]*(\d+)", result.output)
    lots_match = re.search(r"Lots\s+[^0-9]*(\d+)", result.output)
    assert trades_match and int(trades_match.group(1)) > 0
    assert lots_match and int(lots_match.group(1)) > 0
