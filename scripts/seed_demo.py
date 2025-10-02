"""Seed a demo dataset for the portfolio tool."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from portfolio_tool.core.config import ensure_config
from portfolio_tool.data import JSONRepository, SQLiteRepository

_TZ = ZoneInfo("Australia/Brisbane")

_SAMPLE_TRANSACTIONS = [
    {
        "dt": datetime(2024, 1, 2, 10, 0, tzinfo=_TZ).isoformat(),
        "type": "BUY",
        "symbol": "CSL",
        "qty": 10.0,
        "price": 240.0,
        "fees": 9.95,
        "broker_ref": "DEMO-1",
        "notes": "Initial CSL position",
        "exchange": "ASX",
    },
    {
        "dt": datetime(2024, 3, 15, 11, 0, tzinfo=_TZ).isoformat(),
        "type": "BUY",
        "symbol": "IOZ",
        "qty": 50.0,
        "price": 32.5,
        "fees": 9.95,
        "broker_ref": "DEMO-2",
        "notes": "ETF accumulation",
        "exchange": "ASX",
    },
]

_SAMPLE_PRICE = {
    "symbol": "CSL",
    "asof": datetime(2024, 3, 15, 16, 0, tzinfo=_TZ).isoformat(),
    "price": 245.75,
    "source": "manual_seed",
    "fetched_at": datetime.now(tz=_TZ).isoformat(),
    "stale": 0,
}


def _seed_repo(repo) -> None:
    if repo.list_transactions():
        return
    for txn in _SAMPLE_TRANSACTIONS:
        repo.add_transaction(txn)
    repo.upsert_price(_SAMPLE_PRICE)
    repo.close()


def main() -> None:
    config_path = ensure_config()
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    sqlite_repo = SQLiteRepository(data_dir / "demo.sqlite")
    json_repo = JSONRepository(data_dir / "demo.json")

    _seed_repo(sqlite_repo)
    _seed_repo(json_repo)

    print(f"Config ensured at {config_path}")
    print(f"Seeded demo SQLite database at {sqlite_repo.path}")
    print(f"Seeded demo JSON store at {json_repo.path}")


if __name__ == "__main__":
    main()
