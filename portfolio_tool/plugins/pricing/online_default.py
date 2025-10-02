"""HTTP-powered pricing provider using the Yahoo Finance quote endpoint."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Iterable

import httpx

from .provider_base import ProviderPrice


class OnlineDefaultProvider:
    """Fetch quotes from a public HTTP endpoint with basic retries."""

    name = "online_default"

    def __init__(
        self,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
        base_url: str = "https://query1.finance.yahoo.com/v7/finance/quote",
        retries: int = 2,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=5.0))
        self._base_url = base_url
        self._retries = max(retries, 0)
        self._backoff = max(backoff_seconds, 0.0)

    def fetch(self, symbols: Iterable[str]) -> dict[str, ProviderPrice]:
        symbols_list = [symbol for symbol in symbols if symbol]
        if not symbols_list:
            return {}
        params = {"symbols": ",".join(symbols_list)}
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._retries:
            try:
                with self._client_factory() as client:
                    response = client.get(self._base_url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    return self._parse_response(data)
            except Exception as exc:  # pragma: no cover - defensive loop
                last_exc = exc
                attempt += 1
                if attempt > self._retries:
                    break
                time.sleep(self._backoff)
        if last_exc is not None:
            raise last_exc
        return {}

    def _parse_response(self, payload: dict) -> dict[str, ProviderPrice]:
        quotes = {}
        results = payload.get("quoteResponse", {}).get("result", [])
        for item in results:
            symbol = item.get("symbol")
            price = item.get("regularMarketPrice")
            timestamp = item.get("regularMarketTime")
            if not symbol or price is None or timestamp is None:
                continue
            asof = _timestamp_to_datetime(timestamp)
            quotes[symbol] = ProviderPrice(
                symbol=symbol,
                price=float(price),
                asof=asof,
                source=self.name,
            )
        return quotes


def _timestamp_to_datetime(value: int | float) -> datetime:
    return datetime.fromtimestamp(float(value), tz=timezone.utc)

__all__ = ["OnlineDefaultProvider"]
