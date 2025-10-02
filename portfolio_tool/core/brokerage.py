"""Brokerage allocation helpers."""
from __future__ import annotations

from typing import Iterable


class BrokerageAllocationError(ValueError):
    """Raised when brokerage cannot be allocated."""


def allocate_fees(
    total_fees: float,
    strategy: str,
    legs: Iterable[tuple[str, float]],
) -> dict[str, float]:
    """Allocate brokerage fees according to the configured strategy.

    ``legs`` is an iterable of ``(identifier, notional)`` tuples where ``notional``
    is positive for buy legs and negative for sell legs.  The returned mapping
    contains all identifiers with the allocated fee amount (zero for legs that do
    not participate in the chosen strategy).
    """

    strategy = strategy.upper()
    if strategy not in {"BUY", "SELL", "SPLIT"}:
        raise BrokerageAllocationError(f"Unsupported allocation strategy: {strategy}")

    legs = list(legs)
    if not legs:
        return {}

    def _filter_leg(identifier: str, notional: float) -> bool:
        if strategy == "BUY":
            return notional > 0
        if strategy == "SELL":
            return notional < 0
        return True  # SPLIT

    filtered = [(identifier, amount) for identifier, amount in legs if _filter_leg(identifier, amount)]

    if not filtered:
        raise BrokerageAllocationError("No legs eligible for allocation under strategy")

    total_abs = sum(abs(amount) for _, amount in filtered)
    if total_abs == 0:
        raise BrokerageAllocationError("Eligible legs must have non-zero notional")

    allocation: dict[str, float] = {identifier: 0.0 for identifier, _ in legs}
    if total_fees == 0:
        return allocation

    for identifier, amount in filtered:
        share = abs(amount) / total_abs
        allocation[identifier] = total_fees * share
    return allocation


__all__ = ["allocate_fees", "BrokerageAllocationError"]
