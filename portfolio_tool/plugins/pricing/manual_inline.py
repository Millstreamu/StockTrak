"""Manual inline price provider used for offline workflows."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from zoneinfo import ZoneInfo

from .provider_base import ProviderPrice


class ManualInlineProvider:
    """In-memory provider backed by a mutable mapping of quotes."""

    name = "manual_inline"

    def __init__(
        self,
        quotes: Mapping[str, ProviderPrice] | None = None,
        *,
        timezone: str = "Australia/Brisbane",
    ) -> None:
        self._tz = ZoneInfo(timezone)
        self._quotes: dict[str, ProviderPrice] = dict(quotes or {})

    def set_quote(self, symbol: str, price: float, asof: datetime | None = None) -> None:
        """Update the manual quote cache for *symbol*."""

        asof = (asof or datetime.now(tz=self._tz)).astimezone(self._tz)
        self._quotes[symbol] = ProviderPrice(
            symbol=symbol,
            price=float(price),
            asof=asof,
            source=self.name,
        )

    def fetch(self, symbols: Iterable[str]) -> dict[str, ProviderPrice]:
        return {symbol: self._quotes[symbol] for symbol in symbols if symbol in self._quotes}


__all__ = ["ManualInlineProvider"]
