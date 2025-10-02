"""Pricing subsystem responsible for live quote retrieval and caching."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterable, Mapping

from zoneinfo import ZoneInfo

from ..data.repo_base import BaseRepository
from ..plugins.pricing import ProviderPrice, PriceProvider
from .models import PriceQuote


@dataclass(slots=True)
class CachedRecord:
    symbol: str
    asof: datetime
    price: float
    source: str
    fetched_at: datetime
    stale: bool


class PricingService:
    """Manage price cache persistence and provider integration."""

    def __init__(
        self,
        repo: BaseRepository,
        provider: PriceProvider,
        *,
        cache_ttl_minutes: int = 15,
        stale_price_max_minutes: int = 60,
        timezone: str = "Australia/Brisbane",
        exchange_suffix_map: Mapping[str, str] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.cache_ttl = timedelta(minutes=max(cache_ttl_minutes, 0))
        self.stale_window = timedelta(minutes=max(stale_price_max_minutes, 0))
        self.tz = ZoneInfo(timezone)
        self.exchange_suffix_map = {
            (key or "").upper(): value for key, value in (exchange_suffix_map or {}).items()
        }
        self._now = now_fn or (lambda: datetime.now(tz=self.tz))
        self._exchange_cache: dict[str, str | None] = {}

    # ------------------------------------------------------------------
    def refresh_prices(self, symbols: list[str] | None = None) -> dict[str, PriceQuote]:
        """Fetch latest prices for ``symbols`` and store them in the cache."""

        if symbols is None:
            symbols = []
        fetch_map = self._build_provider_symbol_map(symbols)
        if not fetch_map:
            return {}

        try:
            provider_results = self.provider.fetch(sorted(set(fetch_map.values())))
        except Exception:
            return {}

        now = self._now()
        quotes: dict[str, PriceQuote] = {}
        for symbol, provider_symbol in fetch_map.items():
            data = provider_results.get(provider_symbol)
            if not data:
                continue
            record = self._record_from_provider(symbol, data, now)
            self._persist_record(record)
            quotes[symbol] = self._quote_from_record(record)
        return quotes

    # ------------------------------------------------------------------
    def get_cached(self, symbols: list[str]) -> dict[str, PriceQuote]:
        """Return cached price quotes for the requested ``symbols``."""

        records = self.repo.get_prices(symbols)
        now = self._now()
        quotes: dict[str, PriceQuote] = {}
        for symbol in symbols:
            data = records.get(symbol)
            if not data:
                continue
            record = self._record_from_row(symbol, data)
            stale = record.stale or (now - record.fetched_at) > self.cache_ttl
            stale = stale or (now - record.asof) > self.stale_window
            quotes[symbol] = PriceQuote(
                symbol=symbol,
                asof=record.asof,
                price=record.price,
                source=record.source,
                stale=stale,
            )
        return quotes

    # ------------------------------------------------------------------
    def set_manual(self, symbol: str, price, asof) -> dict[str, PriceQuote]:
        """Set a manual price entry that takes precedence over provider data."""

        now = self._now()
        asof_dt = self._ensure_datetime(asof) if asof else now
        record = CachedRecord(
            symbol=symbol,
            asof=asof_dt.astimezone(self.tz),
            price=float(price),
            source="manual",
            fetched_at=now,
            stale=False,
        )
        self._persist_record(record)
        return {symbol: self._quote_from_record(record)}

    # ------------------------------------------------------------------
    def _ensure_datetime(self, value) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=self.tz)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=self.tz)
        raise TypeError("Expected datetime or ISO8601 string")

    def _record_from_row(self, symbol: str, row: Mapping[str, object]) -> CachedRecord:
        stale_value = row.get("stale", 0)
        try:
            stale_flag = bool(int(stale_value))
        except (TypeError, ValueError):
            stale_flag = bool(stale_value)
        return CachedRecord(
            symbol=symbol,
            asof=self._ensure_datetime(row["asof"]),
            price=float(row["price"]),
            source=str(row["source"]),
            fetched_at=self._ensure_datetime(row["fetched_at"]),
            stale=stale_flag,
        )

    def _persist_record(self, record: CachedRecord) -> None:
        stale_flag = int(record.fetched_at - record.asof > self.stale_window)
        self.repo.upsert_price(
            {
                "symbol": record.symbol,
                "asof": record.asof.isoformat(),
                "price": record.price,
                "source": record.source,
                "fetched_at": record.fetched_at.isoformat(),
                "stale": stale_flag,
            }
        )

    def _quote_from_record(self, record: CachedRecord) -> PriceQuote:
        now = self._now()
        stale = (now - record.fetched_at) > self.cache_ttl
        stale = stale or (now - record.asof) > self.stale_window
        return PriceQuote(
            symbol=record.symbol,
            asof=record.asof,
            price=record.price,
            source=record.source,
            stale=stale,
        )

    def _record_from_provider(
        self, symbol: str, data: ProviderPrice, now: datetime
    ) -> CachedRecord:
        asof = data.asof.astimezone(self.tz)
        return CachedRecord(
            symbol=symbol,
            asof=asof,
            price=data.price,
            source=data.source,
            fetched_at=now,
            stale=False,
        )

    def _build_provider_symbol_map(self, symbols: Iterable[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        if not symbols:
            return mapping
        existing = self.repo.get_prices(symbols)
        for symbol in symbols:
            existing_record = existing.get(symbol)
            if existing_record and existing_record.get("source") == "manual":
                continue
            provider_symbol = self._provider_symbol_for(symbol)
            mapping[symbol] = provider_symbol
        return mapping

    def _provider_symbol_for(self, symbol: str) -> str:
        exchange = self._exchange_for_symbol(symbol)
        suffix = self.exchange_suffix_map.get(exchange.upper()) if exchange else None
        if suffix and not symbol.endswith(suffix):
            return f"{symbol}{suffix}"
        return symbol

    def _exchange_for_symbol(self, symbol: str) -> str | None:
        if symbol in self._exchange_cache:
            return self._exchange_cache[symbol]
        rows = self.repo.list_transactions(symbol=symbol, limit=1, order="desc")
        exchange = None
        if rows:
            exchange = rows[0].get("exchange")
        self._exchange_cache[symbol] = exchange.upper() if isinstance(exchange, str) else None
        return self._exchange_cache[symbol]


__all__ = ["PricingService", "CachedRecord"]
