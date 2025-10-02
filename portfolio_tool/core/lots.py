"""Lot management utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Lot


class LotMatchingError(ValueError):
    """Raised when disposal matching cannot satisfy the requested quantity."""


@dataclass(slots=True)
class LotEngine:
    """Wrapper around lot matching strategies."""

    method: str

    def match(
        self,
        lots: Iterable[Lot],
        sell_qty: float,
        specific_map: dict[int, float] | None = None,
    ) -> list[tuple[Lot, float]]:
        return match_disposal(list(lots), sell_qty, self.method, specific_map)


def match_disposal(
    lots: list[Lot],
    sell_qty: float,
    method: str,
    specific_map: dict[int, float] | None,
) -> list[tuple[Lot, float]]:
    """Determine which lots satisfy a sell quantity under the requested method."""

    if sell_qty <= 0:
        raise LotMatchingError("Sell quantity must be positive")

    method = method.upper()
    if method not in {"FIFO", "HIFO", "SPECIFIC_ID"}:
        raise LotMatchingError(f"Unsupported lot matching method: {method}")

    open_lots = [lot for lot in lots if lot.qty_remaining > 0]
    if not open_lots:
        raise LotMatchingError("No open lots available for disposal")

    if method == "SPECIFIC_ID":
        if not specific_map:
            raise LotMatchingError("specific_map required for SPECIFIC_ID matching")
        allocations: list[tuple[Lot, float]] = []
        remaining = sell_qty
        matched_ids: set[int] = set()
        for lot in open_lots:
            if lot.lot_id is None:
                raise LotMatchingError("Specific matching requires persisted lot identifiers")
            key = int(lot.lot_id)
            qty = specific_map.get(key)
            if qty is None:
                continue
            if qty <= 0:
                raise LotMatchingError("Specific lot quantities must be positive")
            if qty > lot.qty_remaining + 1e-9:
                raise LotMatchingError("Specific lot quantity exceeds remaining lot balance")
            allocations.append((lot, float(qty)))
            matched_ids.add(key)
            remaining -= qty
        unused = set(int(k) for k in specific_map.keys()) - matched_ids
        if unused:
            raise LotMatchingError("Specific lot allocation references unavailable lots")
        if abs(remaining) > 1e-9:
            raise LotMatchingError("Specific lot allocation does not match sell quantity")
        return allocations

    if method == "FIFO":
        ordered = sorted(open_lots, key=lambda lot: (lot.acquired_at, lot.lot_id or 0))
    else:  # HIFO
        ordered = sorted(
            open_lots,
            key=lambda lot: (
                -(lot.cost_base_total / lot.qty_remaining),
                lot.acquired_at,
                lot.lot_id or 0,
            ),
        )

    allocations = []
    remaining = sell_qty
    for lot in ordered:
        if remaining <= 0:
            break
        take = min(lot.qty_remaining, remaining)
        allocations.append((lot, float(take)))
        remaining -= take

    if remaining > 1e-9:
        raise LotMatchingError("Insufficient quantity across lots to satisfy sale")
    return allocations


__all__ = ["LotEngine", "LotMatchingError", "match_disposal"]
