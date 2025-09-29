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
    return urlopen(request)  # noqa: S310 - simple GET


@dataclass
class AlphaVantageProvider:
    provider_name: str = "alphavantage"
    api_key: str = ""
    base_url: str = "https://www.alphavantage.co/query"
    currency: str = "USD"
    _opener: Callable[[Request], Any] = _default_opener

    def _build_url(self, symbol: str) -> str:
        params = urlencode(
            {
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol,
                "apikey": self.api_key,
                "outputsize": "compact",
            }
        )
        return f"{self.base_url}?{params}"

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
                raise RuntimeError(f"Alpha Vantage HTTP {getattr(response, 'status', 'unknown')}")
            data = response.read()
            return json.loads(data.decode("utf-8"))

    def _parse_quote(self, payload: Any) -> tuple[Decimal, dt.datetime] | None:
        time_series = payload.get("Time Series (Daily)") if isinstance(payload, dict) else None
        if not isinstance(time_series, dict):
            if isinstance(payload, dict) and payload.get("Note"):
                LOGGER.warning("Alpha Vantage rate limit or notice: %s", payload.get("Note"))
            return None

        latest_date: dt.datetime | None = None
        latest_price: Decimal | None = None
        for date_str, values in time_series.items():
            try:
                dt_value = dt.datetime.fromisoformat(date_str)
            except ValueError:
                continue
            if latest_date is None or dt_value > latest_date:
                close_val = values.get("4. close") if isinstance(values, dict) else None
                if close_val is None:
                    continue
                try:
                    latest_price = Decimal(str(close_val))
                except (ArithmeticError, ValueError):
                    continue
                latest_date = dt_value

        if latest_date is None or latest_price is None:
            return None

        return latest_price, latest_date.replace(tzinfo=dt.timezone.utc)

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        results: dict[str, PriceQuote] = {}
        for symbol in symbols:
            try:
                payload = self._fetch(symbol)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Alpha Vantage request failed for %s: %s", symbol, exc)
                continue

            parsed = self._parse_quote(payload)
            if not parsed:
                LOGGER.debug("Alpha Vantage response missing price for %s", symbol)
                continue

            price, asof = parsed
            results[symbol] = PriceQuote(
                symbol=symbol,
                price=price,
                currency=self.currency,
                asof=asof,
                provider=self.provider_name,
            )
        return results


__all__ = ["AlphaVantageProvider"]
