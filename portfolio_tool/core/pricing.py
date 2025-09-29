from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, Protocol

from sqlalchemy.orm import Session

from portfolio_tool.config import Config
from portfolio_tool.data import repo


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
        for symbol in symbols:
            cached = repo.get_price(session, symbol)
            if cached:
                cached.ttl_expires_at = self._ensure_aware(cached.ttl_expires_at)
                cached.asof = self._ensure_aware(cached.asof)
            if cached and cached.ttl_expires_at and cached.ttl_expires_at > now:
                results[symbol] = PriceQuote(
                    symbol=cached.symbol,
                    price=Decimal(cached.price),
                    currency=cached.currency,
                    asof=self._ensure_aware(cached.asof) or now,
                    provider=cached.provider,
                )
            else:
                if cached:
                    results[symbol] = PriceQuote(
                        symbol=cached.symbol,
                        price=Decimal(cached.price),
                        currency=cached.currency,
                        asof=self._ensure_aware(cached.asof) or now,
                        provider=cached.provider,
                    )
                if not self.cfg.offline_mode:
                    to_fetch.append(symbol)
        fetched: dict[str, PriceQuote] = {}
        if to_fetch and not self.cfg.offline_mode:
            try:
                fetched = self.provider.get_last(to_fetch)
            except Exception:
                fetched = {}
        for symbol in symbols:
            if symbol in fetched:
                quote = fetched[symbol]
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
        session.flush()
        return results


__all__ = ["PriceQuote", "PriceProvider", "PriceService"]
