from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Protocol

from sqlalchemy.orm import Session

from portfolio_tool.config import Config
from portfolio_tool.data import repo


LOGGER = logging.getLogger("portfolio_tool.pricing")


@dataclass
class PriceQuote:
    symbol: str
    price: Decimal
    currency: str
    asof: dt.datetime
    provider: str


class PriceProvider(Protocol):
    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        ...


class PriceService:
    def __init__(self, cfg: Config, provider: PriceProvider):
        self.cfg = cfg
        self.provider = provider

    @staticmethod
    def _ensure_aware(value: dt.datetime | None) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    def get_quotes(self, session: Session, symbols: Iterable[str]) -> dict[str, PriceQuote]:
        symbols = [s.upper() for s in symbols]
        results: dict[str, PriceQuote] = {}
        to_fetch: list[str] = []
        now = dt.datetime.now(dt.timezone.utc)
        ttl = dt.timedelta(minutes=self.cfg.price_ttl_minutes)
        LOGGER.debug("Quote request for symbols: %s", symbols)
        for symbol in symbols:
            cached = repo.get_price(session, symbol)
            if cached:
                cached.ttl_expires_at = self._ensure_aware(cached.ttl_expires_at)
                cached.asof = self._ensure_aware(cached.asof)
            if cached and cached.ttl_expires_at and cached.ttl_expires_at > now:
                LOGGER.debug("Using fresh cached quote for %s (expires %s)", symbol, cached.ttl_expires_at)
                results[symbol] = PriceQuote(
                    symbol=cached.symbol,
                    price=Decimal(cached.price),
                    currency=cached.currency,
                    asof=self._ensure_aware(cached.asof) or now,
                    provider=cached.provider,
                )
            else:
                if cached:
                    LOGGER.debug("Cached quote for %s expired at %s; will mark as stale unless refreshed", symbol, cached.ttl_expires_at)
                    results[symbol] = PriceQuote(
                        symbol=cached.symbol,
                        price=Decimal(cached.price),
                        currency=cached.currency,
                        asof=self._ensure_aware(cached.asof) or now,
                        provider=cached.provider,
                    )
                if not self.cfg.offline_mode:
                    to_fetch.append(symbol)
                else:
                    LOGGER.info("Offline mode enabled; unable to refresh %s", symbol)
        fetched: dict[str, PriceQuote] = {}
        if to_fetch and not self.cfg.offline_mode:
            provider_name = getattr(self.provider, "provider_name", self.provider.__class__.__name__)
            LOGGER.info(
                "Fetching %s symbol(s) from %s: %s",
                len(to_fetch),
                provider_name,
                ", ".join(to_fetch),
            )
            try:
                fetched = self.provider.get_last(to_fetch)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Provider fetch failed for %s: %s", to_fetch, exc, exc_info=True)
                fetched = {}
        for symbol in symbols:
            if symbol in fetched:
                quote = fetched[symbol]
                LOGGER.debug(
                    "Received quote for %s @ %s from %s", symbol, quote.asof.isoformat(), quote.provider
                )
                repo.upsert_price(
                    session,
                    symbol=symbol,
                    price=quote.price,
                    currency=quote.currency,
                    asof=quote.asof,
                    provider=quote.provider,
                    ttl_expires_at=quote.asof + ttl,
                    is_stale=False,
                )
                results[symbol] = quote
            else:
                cached = repo.get_price(session, symbol)
                if cached:
                    cached.ttl_expires_at = self._ensure_aware(cached.ttl_expires_at)
                    cached.asof = self._ensure_aware(cached.asof)
                    cached.is_stale = True
                    LOGGER.debug(
                        "Serving stale cached quote for %s from %s", symbol, cached.asof or now
                    )
                    repo.upsert_price(
                        session,
                        symbol=cached.symbol,
                        price=Decimal(cached.price),
                        currency=cached.currency,
                        asof=self._ensure_aware(cached.asof) or now,
                        provider=cached.provider,
                        ttl_expires_at=self._ensure_aware(cached.ttl_expires_at) or now,
                        is_stale=True,
                    )
                else:
                    LOGGER.warning("No cached quote available for %s", symbol)
        session.flush()
        LOGGER.debug("Completed quote refresh for symbols: %s", symbols)
        return results


__all__ = ["PriceQuote", "PriceProvider", "PriceService"]
