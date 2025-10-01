from __future__ import annotations

from decimal import Decimal

from typer.testing import CliRunner
from sqlalchemy import create_engine, select

from portfolio_tool.__main__ import app
from portfolio_tool.data import models
from portfolio_tool.data.repo import Database


def test_cli_add_trade(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine)

    monkeypatch.setattr("portfolio_tool.__main__.ensure_db", lambda: engine)

    responses = iter(
        [
            "BUY",
            "ABC",
            "2024-01-01T10:00:00+10:00",
            "10",
            "5.50",
            "1.25",
            "ASX",
            "Test trade",
        ]
    )

    def fake_prompt(*args, **kwargs):
        try:
            return next(responses)
        except StopIteration:
            raise AssertionError("Unexpected prompt call") from None

    monkeypatch.setattr("portfolio_tool.__main__.typer.prompt", fake_prompt)

    runner = CliRunner()

    result = runner.invoke(
        app,
        ["add-trade"],
    )

    assert result.exit_code == 0, result.output
    assert "Created BUY trade" in result.output

    db = Database(engine)
    with db.session_scope() as session:
        trades = list(session.scalars(select(models.Trade)))
        assert len(trades) == 1
        trade = trades[0]
        assert trade.side == "BUY"
        assert trade.symbol == "ABC"
        assert trade.qty == Decimal("10")
        assert trade.price == Decimal("5.50")
        assert trade.fees == Decimal("1.25")
        lots = list(session.scalars(select(models.Lot)))
        assert len(lots) == 1
        lot = lots[0]
        assert lot.trade_id == trade.id
        assert lot.qty_remaining == trade.qty
