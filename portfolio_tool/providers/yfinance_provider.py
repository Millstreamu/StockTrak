from __future__ import annotations

import datetime as dt
from decimal import Decimal

import yfinance as yf

from portfolio_tool.core.pricing import PriceQuote


class YFinanceProvider:
    provider_name = "yfinance"

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        results: dict[str, PriceQuote] = {}
        now = dt.datetime.now(dt.timezone.utc)
        if not symbols:
            return results
        data = yf.download(symbols, period="1d", interval="1d", progress=False, auto_adjust=False)
        if hasattr(data, "empty") and data.empty:
            return results
        if hasattr(data, "columns") and ("Close" in data.columns or isinstance(data.columns, tuple)):
            close_data = data["Close"]
            if getattr(close_data, "columns", None) is not None:
                for symbol in symbols:
                    if symbol in close_data.columns:
                        price = Decimal(str(close_data[symbol].iloc[-1]))
                        results[symbol] = PriceQuote(
                            symbol=symbol,
                            price=price,
                            currency="USD",
                            asof=now,
                            provider=self.provider_name,
                        )
                return results
            if not getattr(close_data, "empty", True):
                price = Decimal(str(close_data.iloc[-1]))
                results[symbols[0]] = PriceQuote(
                    symbol=symbols[0],
                    price=price,
                    currency="USD",
                    asof=now,
                    provider=self.provider_name,
                )
                return results
        # fallback per symbol
        for symbol in symbols:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            if hist.empty:
                continue
            price = Decimal(str(hist["Close"].iloc[-1]))
            results[symbol] = PriceQuote(
                symbol=symbol,
                price=price,
                currency="USD",
                asof=now,
                provider=self.provider_name,
            )
        return results


__all__ = ["YFinanceProvider"]
