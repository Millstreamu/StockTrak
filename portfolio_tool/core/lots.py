from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Sequence

from sqlalchemy.orm import Session

from .cgt import compute_disposal


@dataclass
class LotSlice:
    lot: any
    qty: Decimal


@dataclass
class MatchedPiece:
    lot_id: int
    qty: Decimal


def _sort_lots(lots: Sequence, method: str, specific_ids: Sequence[int] | None = None) -> List:
    method = method.upper()
    if method == "FIFO":
        return sorted(lots, key=lambda l: (l.acquired_at, l.id))
    if method == "HIFO":
        return sorted(
            lots,
            key=lambda l: (Decimal(l.cost_base_total) / Decimal(l.qty_remaining), l.acquired_at),
            reverse=True,
        )
    if method == "SPECIFIC_ID":
        if not specific_ids:
            raise ValueError("specific_ids required for SPECIFIC_ID matching")
        id_order = {lot_id: idx for idx, lot_id in enumerate(specific_ids)}
        return sorted(lots, key=lambda l: id_order.get(l.id, len(id_order)))
    raise ValueError(f"Unknown lot matching method {method}")


def match_disposal(
    lots: Sequence,
    sell_qty: Decimal,
    method: str,
    specific_ids: Sequence[int] | None = None,
) -> list[LotSlice]:
    remaining = sell_qty
    ordered = _sort_lots(lots, method, specific_ids)
    slices: list[LotSlice] = []
    for lot in ordered:
        if remaining <= Decimal("0"):
            break
        take = min(remaining, Decimal(lot.qty_remaining))
        if take <= Decimal("0"):
            continue
        slices.append(LotSlice(lot=lot, qty=take))
        remaining -= take
    if remaining > Decimal("0"):
        raise ValueError("Not enough quantity to match disposal")
    return slices


def apply_disposal(
    session: Session,
    lot_slices: Sequence[LotSlice],
    sell_trade,
    sell_qty: Decimal,
    sell_price: Decimal,
    fees_alloc: Decimal,
    tz: str,
):
    for lot_slice in lot_slices:
        lot = lot_slice.lot
        breakdown = compute_disposal(
            lot_id=lot.id,
            qty=lot_slice.qty,
            sell_price=sell_price,
            sell_fees_alloc=fees_alloc * (lot_slice.qty / sell_qty) if sell_qty else Decimal("0"),
            lot_cost_base=Decimal(lot.cost_base_total),
            lot_qty=Decimal(lot.qty_remaining),
            acquired_at=lot.acquired_at,
            disposal_dt=sell_trade.dt,
            tz=tz,
        )
        lot.qty_remaining = Decimal(lot.qty_remaining) - lot_slice.qty
        lot.cost_base_total = Decimal(lot.cost_base_total) - breakdown.cost_base
        session.add(breakdown_to_model(breakdown, sell_trade.id))
        session.flush()
        session.refresh(lot)


def breakdown_to_model(breakdown, sell_trade_id: int):
    from portfolio_tool.data import models

    return models.Disposal(
        sell_trade_id=sell_trade_id,
        lot_id=breakdown.lot_id,
        qty=breakdown.qty,
        proceeds=breakdown.proceeds,
        cost_base_alloc=breakdown.cost_base,
        gain_loss=breakdown.gain_loss,
        eligible_discount=breakdown.eligible_discount,
    )


__all__ = ["match_disposal", "LotSlice", "apply_disposal", "MatchedPiece"]
