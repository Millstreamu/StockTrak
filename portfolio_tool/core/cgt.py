"""Capital gains tax helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from zoneinfo import ZoneInfo

from .models import Disposal, Lot, Transaction


def cgt_threshold(acquired_at: datetime, tz: str) -> datetime:
    """Return the CGT discount threshold date in the configured timezone."""

    aware_acquired = acquired_at.astimezone(ZoneInfo(tz))
    return aware_acquired + timedelta(days=365)


@dataclass(slots=True)
class CGTEngine:
    """Computes disposal slices and discount eligibility."""

    timezone: str

    def slice_disposal(
        self,
        sell_txn: Transaction,
        allocations: Iterable[tuple[Lot, float]],
        fees_allocated: float = 0.0,
    ) -> list[Disposal]:
        if sell_txn.type.upper() != "SELL":
            raise ValueError("Disposals can only be generated for SELL transactions")

        allocations = list(allocations)
        if not allocations:
            return []

        total_qty = sum(qty for _, qty in allocations)
        if total_qty <= 0:
            raise ValueError("Total disposal quantity must be positive")
        fee_per_unit = fees_allocated / total_qty if fees_allocated else 0.0

        tzinfo = ZoneInfo(self.timezone)
        sell_dt = sell_txn.dt.astimezone(tzinfo)
        slices: list[Disposal] = []
        for lot, qty in allocations:
            if qty <= 0:
                raise ValueError("Disposal allocation quantities must be positive")
            if lot.qty_remaining <= 0:
                raise ValueError("Cannot dispose from an exhausted lot")
            cost_per_unit = lot.cost_base_total / lot.qty_remaining
            cost_alloc = cost_per_unit * qty
            gross_proceeds = sell_txn.price * qty
            fee_share = fee_per_unit * qty
            net_proceeds = gross_proceeds - fee_share
            threshold = lot.threshold_date.astimezone(tzinfo) if lot.threshold_date else None
            eligible = threshold is not None and sell_dt >= threshold
            gain_loss = net_proceeds - cost_alloc
            slices.append(
                Disposal(
                    sell_txn_id=sell_txn.id,
                    lot_id=lot.lot_id,
                    qty=qty,
                    proceeds=net_proceeds,
                    cost_base_alloc=cost_alloc,
                    gain_loss=gain_loss,
                    eligible_for_discount=eligible,
                )
            )
        return slices


__all__ = ["cgt_threshold", "CGTEngine"]
