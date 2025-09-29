from __future__ import annotations

import datetime as dt
from decimal import Decimal

from yahooquery import Ticker

from portfolio_tool.core.pricing import PriceQuote


class YahooQueryProvider:
    provider_name = "yahooquery"

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        results: dict[str, PriceQuote] = {}
        if not symbols:
            return results
        tick = Ticker(symbols)
        prices = tick.price
        now = dt.datetime.now(dt.timezone.utc)
        if isinstance(prices, dict):
            for symbol in symbols:
                info = prices.get(symbol)
                if not info:
                    continue
                price = info.get("regularMarketPrice")
                currency = info.get("currency", "USD")
                if price is None:
                    continue
                results[symbol] = PriceQuote(
                    symbol=symbol,
                    price=Decimal(str(price)),
                    currency=currency,
                    asof=now,
                    provider=self.provider_name,
                )
        return results


__all__ = ["YahooQueryProvider"]
