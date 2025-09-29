from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo


@dataclass
class DisposalBreakdown:
    lot_id: int
    qty: Decimal
    proceeds: Decimal
    cost_base: Decimal
    gain_loss: Decimal
    eligible_discount: bool
    threshold_date: dt.date


def cgt_threshold(acquired_at: dt.datetime, tz: str) -> dt.date:
    tzinfo = ZoneInfo(tz)
    local_date = acquired_at.astimezone(tzinfo).date()
    return local_date + dt.timedelta(days=365)


def compute_disposal(
    lot_id: int,
    qty: Decimal,
    sell_price: Decimal,
    sell_fees_alloc: Decimal,
    lot_cost_base: Decimal,
    lot_qty: Decimal,
    acquired_at: dt.datetime,
    disposal_dt: dt.datetime,
    tz: str,
) -> DisposalBreakdown:
    proceeds = qty * sell_price - sell_fees_alloc
    cost_ratio = qty / lot_qty
    cost_base = lot_cost_base * cost_ratio
    gain_loss = proceeds - cost_base
    threshold_date = cgt_threshold(acquired_at, tz)
    eligible_discount = disposal_dt.astimezone(ZoneInfo(tz)).date() > threshold_date
    return DisposalBreakdown(
        lot_id=lot_id,
        qty=qty,
        proceeds=proceeds,
        cost_base=cost_base,
        gain_loss=gain_loss,
        eligible_discount=eligible_discount,
        threshold_date=threshold_date,
    )


__all__ = ["DisposalBreakdown", "cgt_threshold", "compute_disposal"]
