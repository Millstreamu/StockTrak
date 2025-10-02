"""Performance-focused tests (skipped on CI by default)."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from portfolio_tool.core.services import PortfolioService
from portfolio_tool.data.repo_sqlite import SQLiteRepository


@pytest.mark.performance
@pytest.mark.skipif(os.getenv("CI"), reason="Performance tests are skipped on CI")
def test_positions_snapshot_under_five_seconds(tmp_path):
    db_path = tmp_path / "perf.sqlite"
    repo = SQLiteRepository(db_path)
    try:
        tz = ZoneInfo("Australia/Brisbane")
        start_dt = datetime(2018, 1, 2, 10, 0, tzinfo=tz)
        symbols = ["CSL", "BHP", "IOZ", "VAS", "APT", "WES", "TLS", "CBA"]
        lot_rows: list[tuple] = []
        for idx in range(50_000):
            symbol = symbols[idx % len(symbols)]
            acquired = start_dt + timedelta(minutes=idx % 240, days=idx // len(symbols))
            qty = float(5 + (idx % 25))
            cost = qty * (20.0 + (idx % 17))
            threshold = acquired + timedelta(days=365)
            lot_rows.append(
                (
                    symbol,
                    acquired.isoformat(),
                    qty,
                    cost,
                    threshold.isoformat(),
                    None,
                )
            )

        repo._conn.executemany(  # type: ignore[attr-defined]
            """
            INSERT INTO lots (
                symbol,
                acquired_at,
                qty_remaining,
                cost_base_total,
                threshold_date,
                source_txn_id
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            lot_rows,
        )
        repo._conn.commit()  # type: ignore[attr-defined]

        service = PortfolioService(repo)

        start = time.perf_counter()
        positions = service.compute_positions()
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"positions snapshot exceeded budget: {elapsed:.2f}s"
        assert len(positions) == len(symbols)
    finally:
        repo.close()
