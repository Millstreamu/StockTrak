from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from portfolio_tool.core.pricing import PriceQuote


LOGGER = logging.getLogger(__name__)


def _default_opener(request: Request):
    return urlopen(request)  # noqa: S310 - read-only GET request


@dataclass
class MarketIndexProvider:
    provider_name: str = "marketindex"
    base_url: str = "https://data-api.marketindex.com.au"
    base_currency: str = "AUD"
    _opener: Callable[[Request], Any] = _default_opener

    def _build_url(self, symbol: str) -> str:
        params = urlencode({"search": symbol})
        return f"{self.base_url.rstrip('/')}/v1/search?{params}"

    def _fetch(self, symbol: str) -> Any:
        url = self._build_url(symbol)
        request = Request(
            url,
            headers={
                "User-Agent": "StockTrak/1.0 (+https://github.com/StockTrak)",
                "Accept": "application/json",
            },
        )
        with self._opener(request) as response:
            if getattr(response, "status", 200) != 200:
                raise RuntimeError(f"Market Index HTTP {getattr(response, 'status', 'unknown')}")
            payload = response.read()
            return json.loads(payload.decode("utf-8"))

    def _iter_dicts(self, payload: Any):
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from self._iter_dicts(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_dicts(item)

    def _extract_entry(self, symbol: str, payload: Any) -> dict[str, Any] | None:
        symbol_upper = symbol.upper()
        for entry in self._iter_dicts(payload):
            entry_symbol = entry.get("symbol") or entry.get("code") or entry.get("ticker")
            if entry_symbol and str(entry_symbol).upper() == symbol_upper:
                return entry
        return None

    @staticmethod
    def _parse_price(entry: dict[str, Any]) -> Decimal | None:
        for key in ("last_price", "lastPrice", "price", "lastTradePrice", "closePrice"):
            value = entry.get(key)
            if value is not None:
                try:
                    return Decimal(str(value))
                except (ArithmeticError, ValueError):
                    continue
        return None

    @staticmethod
    def _parse_datetime(entry: dict[str, Any]) -> dt.datetime | None:
        for key in ("last_trade_time", "lastTradeDate", "lastUpdated", "priceDate"):
            value = entry.get(key)
            if not value:
                continue
            if isinstance(value, dt.datetime):
                dt_value = value
            else:
                text = str(value)
                if text.endswith("Z"):
                    text = text.replace("Z", "+00:00")
                try:
                    dt_value = dt.datetime.fromisoformat(text)
                except ValueError:
                    continue
            if dt_value.tzinfo is None:
                dt_value = dt_value.replace(tzinfo=dt.timezone.utc)
            return dt_value.astimezone(dt.timezone.utc)
        return None

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        results: dict[str, PriceQuote] = {}
        now = dt.datetime.now(dt.timezone.utc)
        for symbol in symbols:
            try:
                payload = self._fetch(symbol)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Market Index lookup failed for %s: %s", symbol, exc)
                continue

            entry = self._extract_entry(symbol, payload)
            if not entry:
                LOGGER.debug("Market Index entry not found for %s", symbol)
                continue

            price = self._parse_price(entry)
            if price is None:
                LOGGER.debug("Market Index price missing for %s", symbol)
                continue

            asof = self._parse_datetime(entry) or now
            results[symbol] = PriceQuote(
                symbol=symbol,
                price=price,
                currency=self.base_currency,
                asof=asof,
                provider=self.provider_name,
            )
        return results


__all__ = ["MarketIndexProvider"]
