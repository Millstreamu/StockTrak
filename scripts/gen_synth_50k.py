"""Generate deterministic synthetic datasets for performance testing."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from random import Random
from zoneinfo import ZoneInfo

from portfolio_tool.data import JSONRepository, SQLiteRepository

_TZ = ZoneInfo("Australia/Brisbane")
_SYMBOLS = ["CSL", "BHP", "IOZ", "VAS", "APT", "WES", "TLS", "CBA"]
_BASE_PRICES = {
    "CSL": 240.0,
    "BHP": 42.5,
    "IOZ": 32.0,
    "VAS": 90.0,
    "APT": 75.0,
    "WES": 48.0,
    "TLS": 4.2,
    "CBA": 100.0,
}


def _synth_transactions(count: int, seed: int = 2024):
    rng = Random(seed)
    start = datetime(2012, 1, 3, 10, 0, tzinfo=_TZ)
    for idx in range(count):
        symbol = _SYMBOLS[idx % len(_SYMBOLS)]
        side_toggle = idx % 5
        txn_type = "BUY" if side_toggle < 3 else "SELL"
        qty = float((rng.randint(1, 25) * 5) if txn_type == "BUY" else (rng.randint(1, 10) * 5))
        base = _BASE_PRICES[symbol]
        price_variation = 1 + rng.uniform(-0.12, 0.12)
        price = round(base * price_variation, 4)
        dt = start + timedelta(days=idx // len(_SYMBOLS), minutes=idx % 360)
        yield {
            "dt": dt.isoformat(),
            "type": txn_type,
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "fees": round(4.5 + qty * 0.015, 2),
            "broker_ref": f"SYN-{idx:05d}",
            "notes": f"Synthetic trade #{idx}",
            "exchange": "ASX",
        }


def _seed_repo(repo, txns) -> None:
    for txn in txns:
        repo.add_transaction(txn)
    repo.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path("data"), help="Output directory")
    parser.add_argument("--count", type=int, default=50_000, help="Number of trades to generate")
    parser.add_argument(
        "--backends",
        nargs="+",
        choices=["sqlite", "json"],
        default=["sqlite", "json"],
        help="Backends to generate",
    )
    args = parser.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)

    txns = list(_synth_transactions(args.count))

    if "sqlite" in args.backends:
        sqlite_path = args.dir / "synth.sqlite"
        if sqlite_path.exists():
            sqlite_path.unlink()
        sqlite_repo = SQLiteRepository(sqlite_path)
        _seed_repo(sqlite_repo, txns)
        print(f"Generated SQLite dataset: {sqlite_path} ({args.count} txns)")

    if "json" in args.backends:
        json_path = args.dir / "synth.json"
        if json_path.exists():
            json_path.unlink()
        json_repo = JSONRepository(json_path)
        _seed_repo(json_repo, txns)
        print(f"Generated JSON dataset: {json_path} ({args.count} txns)")


if __name__ == "__main__":
    main()
