from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Dict

from portfolio_tool.config import Config
from portfolio_tool.core.pricing import PriceProvider, PriceQuote
from typing import TYPE_CHECKING

from portfolio_tool.providers.alphavantage_provider import AlphaVantageProvider
from portfolio_tool.providers.marketindex_provider import MarketIndexProvider

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from portfolio_tool.providers.yahooquery_provider import YahooQueryProvider
    from portfolio_tool.providers.yfinance_provider import YFinanceProvider


LOGGER = logging.getLogger(__name__)


class FallbackPriceProvider:
    """Coordinate primary and fallback providers with symbol normalisation."""

    def __init__(
        self,
        cfg: Config,
        providers: Dict[str, PriceProvider | None] | None = None,
    ) -> None:
        self.cfg = cfg
        self._providers: Dict[str, PriceProvider | None] = providers or {}

    # -- provider orchestration -------------------------------------------------
    def _provider_order(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for name in [self.cfg.pricing.provider_primary, *self.cfg.pricing.fallbacks]:
            if name and name not in seen:
                names.append(name)
                seen.add(name)
        return names

    def _build_provider(self, name: str) -> PriceProvider | None:
        match name:
            case "yfinance":
                try:
                    from portfolio_tool.providers.yfinance_provider import (
                        YFinanceProvider,
                    )
                except ModuleNotFoundError as exc:  # pragma: no cover - optional dep
                    missing_dep = exc.name or "yfinance"
                    LOGGER.info(
                        "Skipping yfinance provider: optional dependency '%s' is not installed",
                        missing_dep,
                    )
                    return None
                return YFinanceProvider()
            case "yahooquery":
                try:
                    from portfolio_tool.providers.yahooquery_provider import (
                        YahooQueryProvider,
                    )
                except ModuleNotFoundError as exc:  # pragma: no cover - optional dep
                    missing_dep = exc.name or "yahooquery"
                    LOGGER.info(
                        "Skipping yahooquery provider: optional dependency '%s' is not installed",
                        missing_dep,
                    )
                    return None
                return YahooQueryProvider()
            case "marketindex":
                if not self.cfg.pricing.include_marketindex:
                    LOGGER.info(
                        "Market Index fallback is disabled; set pricing.include_marketindex=true to enable"
                    )
                    return None
                LOGGER.warning(
                    "Using Market Index data API fallback. This is an undocumented endpoint and may change."
                )
                return MarketIndexProvider(base_currency=self.cfg.base_currency)
            case "alphavantage":
                api_key = self.cfg.alpha_vantage.api_key
                if not api_key:
                    LOGGER.info("Alpha Vantage fallback skipped: api key not configured")
                    return None
                return AlphaVantageProvider(api_key=api_key, currency=self.cfg.base_currency)
            case _:
                LOGGER.warning("Unknown price provider '%s'", name)
                return None

    def _get_provider(self, name: str) -> PriceProvider | None:
        if name not in self._providers:
            provider = self._build_provider(name)
            if provider:
                self._providers[name] = provider
            else:
                self._providers[name] = None  # cache skip
        return self._providers.get(name)

    # -- symbol handling --------------------------------------------------------
    def _symbol_candidates(self, symbol: str) -> list[str]:
        candidates: "OrderedDict[str, None]" = OrderedDict()
        candidates[symbol] = None
        if (
            self.cfg.pricing.normalize_asx_suffix
            and "." not in symbol
            and self.cfg.timezone.lower().startswith("australia")
        ):
            candidates[f"{symbol}.AX"] = None
        return list(candidates.keys())

    # -- public api -------------------------------------------------------------
    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        if not symbols:
            return {}

        normalised: dict[str, list[str]] = {s: self._symbol_candidates(s) for s in symbols}
        results: dict[str, PriceQuote] = {}
        remaining = set(symbols)

        for provider_name in self._provider_order():
            if not remaining:
                break
            provider = self._get_provider(provider_name)
            if not provider:
                continue

            query_symbols = []
            for symbol in remaining:
                query_symbols.extend(normalised[symbol])
            # preserve order while deduping
            seen: set[str] = set()
            ordered_query = [
                sym for sym in query_symbols if not (sym in seen or seen.add(sym))
            ]

            try:
                provider_results = provider.get_last(ordered_query)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Price provider %s failed: %s", provider_name, exc)
                continue

            for original_symbol in list(remaining):
                for candidate in normalised[original_symbol]:
                    quote = provider_results.get(candidate)
                    if quote:
                        if candidate != original_symbol:
                            LOGGER.info(
                                "Normalised %s -> %s via %s", original_symbol, candidate, provider_name
                            )
                        results[original_symbol] = PriceQuote(
                            symbol=original_symbol,
                            price=quote.price,
                            currency=quote.currency,
                            asof=quote.asof,
                            provider=quote.provider,
                        )
                        remaining.remove(original_symbol)
                        break

        if remaining:
            LOGGER.warning(
                "No live price after fallbacks for: %s", ", ".join(sorted(remaining))
            )

        return results


__all__ = ["FallbackPriceProvider"]
