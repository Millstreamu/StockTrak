"""Price provider protocol definitions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


@dataclass(slots=True)
class ProviderPrice:
    """Container returned by price providers."""

    symbol: str
    price: float
    asof: datetime
    source: str


class PriceProvider(Protocol):
    """Protocol implemented by pricing provider plugins."""

    name: str

    def fetch(self, symbols: Iterable[str]) -> dict[str, ProviderPrice]:
        """Return price quotes keyed by the provider's symbol string."""


__all__ = ["ProviderPrice", "PriceProvider"]
