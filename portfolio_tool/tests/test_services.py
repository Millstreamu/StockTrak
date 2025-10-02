from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from portfolio_tool.core.models import Transaction
from portfolio_tool.core.services import PortfolioService
from portfolio_tool.data.repo_json import JSONRepository


def aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=ZoneInfo("Australia/Brisbane"))


def test_portfolio_service_buy_then_sell_updates_lots(tmp_path):
    repo_path = tmp_path / "repo.json"
    service = PortfolioService(JSONRepository(repo_path))

    buy_txn = Transaction(
        dt=aware(datetime(2023, 1, 1, 10, 0)),
        type="BUY",
        symbol="CSL",
        qty=100.0,
        price=10.0,
        fees=5.0,
    )
    buy_id = service.record_trade(buy_txn)
    assert buy_id == 1
    repo = service.repo
    open_lots = repo.list_lots(symbol="CSL", only_open=True)
    assert len(open_lots) == 1
    assert open_lots[0]["qty_remaining"] == pytest.approx(100.0)
    assert open_lots[0]["cost_base_total"] == pytest.approx(1005.0)

    sell_txn = Transaction(
        dt=aware(datetime(2023, 6, 1, 11, 0)),
        type="SELL",
        symbol="CSL",
        qty=40.0,
        price=12.0,
        fees=0.0,
    )
    sell_id = service.record_trade(sell_txn)
    assert sell_id == 2

    open_lots = repo.list_lots(symbol="CSL", only_open=True)
    assert open_lots[0]["qty_remaining"] == pytest.approx(60.0)
    assert open_lots[0]["cost_base_total"] == pytest.approx(603.0)

    disposals = repo.list_disposals(sell_txn_id=sell_id)
    assert len(disposals) == 1
    assert disposals[0]["proceeds"] == pytest.approx(480.0)
    assert disposals[0]["cost_base_alloc"] == pytest.approx(402.0)
    assert disposals[0]["gain_loss"] == pytest.approx(78.0)

    positions = service.compute_positions(prices={"CSL": 15.0})
    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "CSL"
    assert pos.total_qty == pytest.approx(60.0)
    assert pos.avg_cost == pytest.approx(603.0 / 60.0)
    assert pos.mv == pytest.approx(900.0)
    assert pos.weight == pytest.approx(1.0)
