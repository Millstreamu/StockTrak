from __future__ import annotations

import datetime as dt
from decimal import Decimal

from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.data import repo


class DummyProvider:
    def __init__(self, price: str = "100") -> None:
        self.price = Decimal(price)
        self.call_count = 0
        self.raise_error = False

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        self.call_count += 1
        if self.raise_error:
            raise RuntimeError("provider down")
        now = dt.datetime.now(dt.timezone.utc)
        return {
            symbol: PriceQuote(
                symbol=symbol,
                price=self.price,
                currency="USD",
                asof=now,
                provider="dummy",
            )
            for symbol in symbols
        }


def test_price_caching_respects_ttl(cfg, db):
    provider = DummyProvider("123")
    service = PriceService(cfg, provider)
    with db.session_scope() as session:
        quotes = service.get_quotes(session, ["AAA"])
        assert provider.call_count == 1
        quotes = service.get_quotes(session, ["AAA"])
        assert provider.call_count == 1
        assert quotes["AAA"].price == Decimal("123")


def test_price_fallback_marks_stale(cfg, db):
    provider = DummyProvider("50")
    service = PriceService(cfg, provider)
    with db.session_scope() as session:
        service.get_quotes(session, ["BBB"])
        cached = repo.get_price(session, "BBB")
        cached.ttl_expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        provider.raise_error = True
        quotes = service.get_quotes(session, ["BBB"])
        cached = repo.get_price(session, "BBB")
        assert cached.is_stale is True
        assert quotes["BBB"].price == Decimal("50")
        assert provider.call_count == 2
