from __future__ import annotations

import datetime as dt
from decimal import Decimal

from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.data import repo
from portfolio_tool.providers.fallback_provider import FallbackPriceProvider


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


class StubProvider:
    def __init__(self, name: str, prices: dict[str, str | Decimal]):
        self.provider_name = name
        self.prices = {k: Decimal(str(v)) for k, v in prices.items()}
        self.calls: list[list[str]] = []

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        self.calls.append(list(symbols))
        now = dt.datetime.now(dt.timezone.utc)
        results: dict[str, PriceQuote] = {}
        for symbol in symbols:
            price = self.prices.get(symbol)
            if price is None:
                continue
            results[symbol] = PriceQuote(
                symbol=symbol,
                price=price,
                currency="AUD",
                asof=now,
                provider=self.provider_name,
            )
        return results


class EmptyProvider:
    provider_name = "empty"

    def __init__(self):
        self.calls: list[list[str]] = []

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        self.calls.append(list(symbols))
        return {}


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


def test_fallback_normalises_asx_symbol(cfg):
    cfg.timezone = "Australia/Sydney"
    yfinance = StubProvider("yfinance", {"CSL.AX": "260.5"})
    provider = FallbackPriceProvider(cfg, providers={"yfinance": yfinance})
    quotes = provider.get_last(["CSL"])
    assert "CSL" in quotes
    assert quotes["CSL"].symbol == "CSL"
    assert quotes["CSL"].provider == "yfinance"
    assert any("CSL.AX" in call for call in yfinance.calls)


def test_fallback_uses_yahooquery_when_primary_empty(cfg):
    cfg.timezone = "Australia/Melbourne"
    yfinance = EmptyProvider()
    yahoo = StubProvider("yahooquery", {"ABC.AX": "12.34"})
    provider = FallbackPriceProvider(
        cfg,
        providers={"yfinance": yfinance, "yahooquery": yahoo},
    )
    quotes = provider.get_last(["ABC"])
    assert "ABC" in quotes
    assert quotes["ABC"].provider == "yahooquery"
    assert quotes["ABC"].price == Decimal("12.34")
    assert yfinance.calls  # primary attempted first


def test_marketindex_optional_fallback(cfg):
    cfg.timezone = "Australia/Perth"
    cfg.pricing.include_marketindex = True
    yfinance = EmptyProvider()
    yahoo = EmptyProvider()
    market = StubProvider("marketindex", {"XYZ.AX": "7.89"})
    provider = FallbackPriceProvider(
        cfg,
        providers={
            "yfinance": yfinance,
            "yahooquery": yahoo,
            "marketindex": market,
        },
    )
    quotes = provider.get_last(["XYZ"])
    assert quotes["XYZ"].provider == "marketindex"
    assert quotes["XYZ"].price == Decimal("7.89")


def test_alphavantage_final_fallback(cfg):
    cfg.timezone = "Australia/Brisbane"
    cfg.alpha_vantage.api_key = "abc"
    cfg.pricing.fallbacks = ["yahooquery", "marketindex", "alphavantage"]
    yfinance = EmptyProvider()
    yahoo = EmptyProvider()
    alpha = StubProvider("alphavantage", {"ZZZ.AX": "15.55"})
    provider = FallbackPriceProvider(
        cfg,
        providers={
            "yfinance": yfinance,
            "yahooquery": yahoo,
            "alphavantage": alpha,
        },
    )
    quotes = provider.get_last(["ZZZ"])
    assert quotes["ZZZ"].provider == "alphavantage"
    assert quotes["ZZZ"].price == Decimal("15.55")


def test_total_failure_returns_stale_from_cache(cfg, db):
    cfg.timezone = "Australia/Sydney"
    provider = FallbackPriceProvider(
        cfg,
        providers={
            "yfinance": EmptyProvider(),
            "yahooquery": EmptyProvider(),
            "marketindex": EmptyProvider(),
            "alphavantage": EmptyProvider(),
        },
    )
    service = PriceService(cfg, provider)
    with db.session_scope() as session:
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        repo.upsert_price(
            session,
            symbol="OLD",
            price=Decimal("99.99"),
            currency="AUD",
            asof=past,
            provider="seed",
            ttl_expires_at=past,
            is_stale=False,
        )
        quotes = service.get_quotes(session, ["OLD"])
        cached = repo.get_price(session, "OLD")
        assert cached.is_stale is True
        assert quotes["OLD"].price == Decimal("99.99")
