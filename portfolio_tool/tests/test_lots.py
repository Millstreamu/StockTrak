from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from portfolio_tool.core.lots import LotMatchingError, match_disposal
from portfolio_tool.core.models import Lot


TZ = ZoneInfo("Australia/Brisbane")


def make_lot(lot_id: int, acquired: datetime, qty: float, cost: float) -> Lot:
    return Lot(
        lot_id=lot_id,
        symbol="CSL",
        acquired_at=acquired,
        qty_remaining=qty,
        cost_base_total=cost,
        threshold_date=acquired + timedelta(days=365),
    )


def test_match_fifo_prefers_oldest_lots():
    lots = [
        make_lot(1, datetime(2023, 1, 1, tzinfo=TZ), 100, 1000),
        make_lot(2, datetime(2023, 2, 1, tzinfo=TZ), 200, 2200),
    ]
    matches = match_disposal(lots, 150, "FIFO", None)
    assert [(lot.lot_id, qty) for lot, qty in matches] == [(1, 100.0), (2, 50.0)]


def test_match_hifo_prefers_high_cost_per_unit():
    lots = [
        make_lot(1, datetime(2023, 1, 1, tzinfo=TZ), 100, 1000),  # cost per unit 10
        make_lot(2, datetime(2023, 1, 5, tzinfo=TZ), 50, 750),  # cost per unit 15
        make_lot(3, datetime(2023, 1, 10, tzinfo=TZ), 75, 600),  # cost per unit 8
    ]
    matches = match_disposal(lots, 60, "HIFO", None)
    assert [(lot.lot_id, qty) for lot, qty in matches] == [(2, 50.0), (1, 10.0)]


def test_match_specific_id_requires_exact_quantities():
    lots = [
        make_lot(1, datetime(2023, 1, 1, tzinfo=TZ), 100, 1000),
        make_lot(2, datetime(2023, 1, 5, tzinfo=TZ), 50, 750),
    ]
    matches = match_disposal(lots, 120, "SPECIFIC_ID", {1: 70, 2: 50})
    assert [(lot.lot_id, qty) for lot, qty in matches] == [(1, 70.0), (2, 50.0)]


def test_match_specific_id_invalid_reference_raises():
    lots = [make_lot(1, datetime(2023, 1, 1, tzinfo=TZ), 100, 1000)]
    with pytest.raises(LotMatchingError):
        match_disposal(lots, 50, "SPECIFIC_ID", {2: 50})


def test_match_raises_on_insufficient_quantity():
    lots = [make_lot(1, datetime(2023, 1, 1, tzinfo=TZ), 100, 1000)]
    with pytest.raises(LotMatchingError):
        match_disposal(lots, 150, "FIFO", None)
