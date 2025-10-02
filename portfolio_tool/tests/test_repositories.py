from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from portfolio_tool.data import JSONRepository, SQLiteRepository

_TZ = ZoneInfo("Australia/Brisbane")


@pytest.fixture(params=["sqlite", "json"])
def repo(tmp_path, request):
    if request.param == "sqlite":
        instance = SQLiteRepository(tmp_path / "test.sqlite")
    else:
        instance = JSONRepository(tmp_path / "test.json")
    yield instance
    instance.close()


def _sample_txn(symbol: str = "CSL") -> dict:
    return {
        "dt": datetime(2024, 1, 2, 10, 0, tzinfo=_TZ).isoformat(),
        "type": "BUY",
        "symbol": symbol,
        "qty": 10.0,
        "price": 240.5,
        "fees": 9.95,
        "broker_ref": "TEST-1",
        "notes": "unit test",
        "exchange": "ASX",
    }


def _sample_lot(symbol: str = "CSL") -> dict:
    return {
        "symbol": symbol,
        "acquired_at": datetime(2024, 1, 2, 10, 0, tzinfo=_TZ).isoformat(),
        "qty_remaining": 10.0,
        "cost_base_total": 2405.0,
        "threshold_date": datetime(2025, 1, 2, 10, 0, tzinfo=_TZ).isoformat(),
        "source_txn_id": 1,
    }


def _sample_disposal(lot_id: int, sell_txn_id: int = 2) -> dict:
    return {
        "sell_txn_id": sell_txn_id,
        "lot_id": lot_id,
        "qty": 5.0,
        "proceeds": 1300.0,
        "cost_base_alloc": 1200.0,
        "gain_loss": 100.0,
        "eligible_for_discount": 1,
    }


def _sample_price(symbol: str = "CSL") -> dict:
    now = datetime(2024, 3, 1, 12, 0, tzinfo=_TZ)
    return {
        "symbol": symbol,
        "asof": now.isoformat(),
        "price": 250.25,
        "source": "unit-test",
        "fetched_at": now.isoformat(),
        "stale": 0,
    }


def _sample_actionable(symbol: str = "CSL") -> dict:
    created = datetime(2024, 2, 15, 9, 0, tzinfo=_TZ).isoformat()
    return {
        "type": "RULE",
        "symbol": symbol,
        "message": "Check position sizing",
        "status": "OPEN",
        "created_at": created,
        "updated_at": created,
        "snoozed_until": None,
        "context": "{}",
    }


def test_transaction_crud(repo):
    txn_id = repo.add_transaction(_sample_txn())
    fetched = repo.get_transaction(txn_id)
    assert fetched["symbol"] == "CSL"
    repo.update_transaction(txn_id, {"notes": "updated"})
    updated = repo.get_transaction(txn_id)
    assert updated["notes"] == "updated"
    repo.delete_transaction(txn_id)
    assert repo.get_transaction(txn_id) is None


def test_list_transactions_order(repo):
    repo.add_transaction(_sample_txn("CSL"))
    second = _sample_txn("BHP")
    second["dt"] = datetime(2024, 1, 3, 10, 0, tzinfo=_TZ).isoformat()
    repo.add_transaction(second)
    rows = repo.list_transactions(order="desc")
    assert rows[0]["symbol"] == "BHP"
    rows_symbol = repo.list_transactions(symbol="CSL")
    assert all(row["symbol"] == "CSL" for row in rows_symbol)


def test_lot_and_disposal_roundtrip(repo):
    lot_id = repo.add_lot(_sample_lot())
    repo.update_lot(lot_id, {"qty_remaining": 4.0})
    lots = repo.list_lots()
    assert lots[0]["qty_remaining"] == 4.0
    open_lots = repo.list_lots(only_open=True)
    assert open_lots
    repo.update_lot(lot_id, {"qty_remaining": 0.0})
    assert repo.list_lots(only_open=True) == []

    disposal_id = repo.add_disposal(_sample_disposal(lot_id))
    disposals = repo.list_disposals(lot_id=lot_id)
    assert disposals[0]["id"] == disposal_id
    repo.delete_disposals_for_sell(_sample_disposal(lot_id)["sell_txn_id"])
    assert repo.list_disposals(lot_id=lot_id) == []


def test_price_cache_roundtrip(repo):
    record = _sample_price()
    repo.upsert_price(record)
    prices = repo.get_prices(["CSL"])
    assert prices["CSL"]["price"] == 250.25
    updated = record | {"price": 260.0, "stale": 1}
    repo.upsert_price(updated)
    prices = repo.get_prices(["CSL"])
    assert prices["CSL"]["price"] == 260.0
    repo.purge_price("CSL")
    assert repo.get_prices(["CSL"]) == {}


def test_actionables_roundtrip(repo):
    actionable_id = repo.add_actionable(_sample_actionable())
    rows = repo.list_actionables()
    assert rows[0]["id"] == actionable_id
    repo.update_actionable(actionable_id, {"status": "DONE", "updated_at": datetime.now(tz=_TZ).isoformat()})
    done = repo.list_actionables(status="DONE")
    assert len(done) == 1
    repo.update_actionable(actionable_id, {"snoozed_until": datetime(2024, 3, 1, tzinfo=_TZ).isoformat()})
    active = repo.list_actionables(include_snoozed=False)
    assert active == []


def test_sqlite_migration_runs(tmp_path):
    db_path = tmp_path / "migrated.sqlite"
    repo = SQLiteRepository(db_path)
    try:
        repo.add_transaction(_sample_txn())
    finally:
        repo.close()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT version FROM schema_migrations")
        versions = {row[0] for row in cur.fetchall()}
    assert "001" in versions


def _summarise(repo):
    txns = repo.list_transactions()
    lots = repo.list_lots()
    disposals = repo.list_disposals()
    prices = repo.get_prices(["CSL"])
    actionables = repo.list_actionables()
    return {
        "transactions": [
            {k: row[k] for k in ("type", "symbol", "qty", "price", "fees")}
            for row in txns
        ],
        "lots": [
            {k: row[k] for k in ("symbol", "qty_remaining", "cost_base_total")}
            for row in lots
        ],
        "disposals": [
            {k: row[k] for k in ("sell_txn_id", "lot_id", "qty", "gain_loss")}
            for row in disposals
        ],
        "prices": {symbol: {"price": rec["price"]} for symbol, rec in prices.items()},
        "actionables": [
            {k: row[k] for k in ("type", "status", "symbol")}
            for row in actionables
        ],
    }


def test_repositories_parity(tmp_path):
    sqlite_repo = SQLiteRepository(tmp_path / "parity.sqlite")
    json_repo = JSONRepository(tmp_path / "parity.json")

    for repo in (sqlite_repo, json_repo):
        txn_id = repo.add_transaction(_sample_txn())
        lot_id = repo.add_lot(_sample_lot())
        repo.add_disposal(_sample_disposal(lot_id, sell_txn_id=txn_id))
        repo.upsert_price(_sample_price())
        repo.add_actionable(_sample_actionable())

    sqlite_state = _summarise(sqlite_repo)
    json_state = _summarise(json_repo)

    sqlite_repo.close()
    json_repo.close()

    assert sqlite_state == json_state
