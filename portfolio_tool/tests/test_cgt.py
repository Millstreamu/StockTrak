from __future__ import annotations

import datetime as dt
from decimal import Decimal

from portfolio_tool.core.cgt import compute_disposal, cgt_threshold


def test_cgt_threshold_handles_leap_year():
    acquired = dt.datetime(2023, 3, 1, 10, tzinfo=dt.timezone.utc)
    threshold = cgt_threshold(acquired, "Australia/Brisbane")
    assert threshold == dt.date(2024, 2, 29)


def test_compute_disposal_discount_flag():
    acquired = dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)
    disposal_dt = dt.datetime(2023, 1, 5, tzinfo=dt.timezone.utc)
    breakdown = compute_disposal(
        lot_id=1,
        qty=Decimal("5"),
        sell_price=Decimal("12"),
        sell_fees_alloc=Decimal("1"),
        lot_cost_base=Decimal("100"),
        lot_qty=Decimal("10"),
        acquired_at=acquired,
        disposal_dt=disposal_dt,
        tz="Australia/Brisbane",
    )
    assert breakdown.eligible_discount is True
    assert breakdown.gain_loss == Decimal("9")
