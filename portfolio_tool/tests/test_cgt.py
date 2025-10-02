from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from portfolio_tool.core.cgt import CGTEngine, cgt_threshold
from portfolio_tool.core.models import Lot, Transaction


TZ = "Australia/Brisbane"


def aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=ZoneInfo(TZ))


def test_cgt_threshold_handles_leap_years():
    acquired = aware(datetime(2020, 2, 29, 10, 30))
    threshold = cgt_threshold(acquired, TZ)
    assert threshold == aware(datetime(2021, 2, 28, 10, 30))


def test_cgt_threshold_converts_from_other_timezone():
    acquired = datetime(2023, 3, 14, 12, 0, tzinfo=ZoneInfo("UTC"))
    threshold = cgt_threshold(acquired, TZ)
    expected = datetime(2024, 3, 13, 22, 0, tzinfo=ZoneInfo(TZ))
    assert threshold == expected


def test_cgt_engine_produces_discount_flag_and_gains():
    engine = CGTEngine(TZ)
    lot = Lot(
        lot_id=5,
        symbol="CSL",
        acquired_at=aware(datetime(2022, 1, 1, 9, 30)),
        qty_remaining=100,
        cost_base_total=1000.0,
        threshold_date=aware(datetime(2023, 1, 1, 9, 30)),
    )
    sell_txn = Transaction(
        id=10,
        dt=aware(datetime(2024, 1, 15, 11, 0)),
        type="SELL",
        symbol="CSL",
        qty=40,
        price=15.0,
        fees=10.0,
    )
    slices = engine.slice_disposal(sell_txn, [(lot, 40.0)], fees_allocated=10.0)
    assert len(slices) == 1
    disposal = slices[0]
    assert disposal.proceeds == pytest.approx(590.0)  # 40 * 15 minus 10 fees
    assert disposal.cost_base_alloc == pytest.approx(400.0)
    assert disposal.gain_loss == pytest.approx(190.0)
    assert disposal.eligible_for_discount is True
