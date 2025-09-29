from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
import logging

try:  # pragma: no cover - import guard is hard to exercise in tests
    import yfinance as yf
except ModuleNotFoundError:  # pragma: no cover - exercised when optional dependency missing
    class _MissingYFinance:
        """Minimal stub used when the optional ``yfinance`` dependency is absent."""

        _error = ModuleNotFoundError(
            "The optional dependency 'yfinance' is required for YFinanceProvider."
            " Install it via 'pip install yfinance' to enable live pricing."
        )

        def download(self, *args, **kwargs):  # noqa: D401 - same behaviour as yfinance
            """Raise an informative error about the missing dependency."""

            raise self._error

        def Ticker(self, *args, **kwargs):  # noqa: N802 - matches yfinance API
            raise self._error

    yf = _MissingYFinance()

from portfolio_tool.core.pricing import PriceQuote


LOGGER = logging.getLogger(__name__)


class YFinanceProvider:
    provider_name = "yfinance"

    @staticmethod
    def _parse_price(value: object) -> Decimal | None:
        try:
            price = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not price.is_finite():
            return None
        return price

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        results: dict[str, PriceQuote] = {}
        now = dt.datetime.now(dt.timezone.utc)
        if not symbols:
            return results
        try:
            data = yf.download(
                symbols,
                period="1d",
                interval="1d",
                progress=False,
                auto_adjust=False,
            )
        except ValueError as exc:
            if "No data" in str(exc) or "decrypt" in str(exc).lower():
                LOGGER.warning("yfinance download returned no data: %s", exc)
                data = None
            else:
                LOGGER.warning("yfinance download error: %s", exc)
                return results
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("yfinance download failed: %s", exc)
            return results
        if hasattr(data, "empty") and data.empty:
            return results
        if hasattr(data, "columns") and ("Close" in data.columns or isinstance(data.columns, tuple)):
            close_data = data["Close"]
            if getattr(close_data, "columns", None) is not None:
                for symbol in symbols:
                    if symbol in close_data.columns:
                        price = self._parse_price(close_data[symbol].iloc[-1])
                        if price is None:
                            continue
                        results[symbol] = PriceQuote(
                            symbol=symbol,
                            price=price,
                            currency="USD",
                            asof=now,
                            provider=self.provider_name,
                        )
                return results
            if not getattr(close_data, "empty", True):
                price = self._parse_price(close_data.iloc[-1])
                if price is not None:
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
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("yfinance history failed for %s: %s", symbol, exc)
                continue
            if getattr(hist, "empty", True):
                continue
            try:
                price = self._parse_price(hist["Close"].iloc[-1])
                if price is None:
                    continue
            except (IndexError, KeyError, ValueError, ArithmeticError) as exc:
                LOGGER.debug("yfinance close extraction failed for %s: %s", symbol, exc)
                continue
            results[symbol] = PriceQuote(
                symbol=symbol,
                price=price,
                currency="USD",
                asof=now,
                provider=self.provider_name,
            )
        return results


__all__ = ["YFinanceProvider"]
