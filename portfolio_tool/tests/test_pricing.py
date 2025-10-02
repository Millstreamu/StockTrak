from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from zoneinfo import ZoneInfo

from portfolio_tool.core.models import Transaction
from portfolio_tool.core.pricing import PricingService
from portfolio_tool.core.services import PortfolioService
from portfolio_tool.data.repo_json import JSONRepository
from portfolio_tool.plugins.pricing import ProviderPrice
from portfolio_tool.plugins.pricing.online_default import OnlineDefaultProvider


class DummyProvider:
    name = "dummy"

    def __init__(self, price: float, *, tz: ZoneInfo) -> None:
        self.tz = tz
        self.price = price
        self.asof = datetime(2024, 1, 1, 10, 0, tzinfo=tz)

    def fetch(self, symbols):
        return {
            symbol: ProviderPrice(
                symbol=symbol,
                price=self.price,
                asof=self.asof,
                source=self.name,
            )
            for symbol in symbols
        }


def _service(tmp_path, provider, now):
    repo = JSONRepository(tmp_path / "pricing.json")
    return repo, PricingService(
        repo,
        provider,
        cache_ttl_minutes=15,
        stale_price_max_minutes=60,
        timezone="Australia/Brisbane",
        now_fn=lambda: now[0],
    )


def aware(year, month, day, hour=0, minute=0):
    tz = ZoneInfo("Australia/Brisbane")
    return datetime(year, month, day, hour, minute, tzinfo=tz)


def test_refresh_and_cache_roundtrip(tmp_path):
    tz = ZoneInfo("Australia/Brisbane")
    provider = DummyProvider(250.0, tz=tz)
    now = [aware(2024, 1, 1, 11, 0)]
    repo, service = _service(tmp_path, provider, now)

    quotes = service.refresh_prices(["CSL"])
    assert quotes["CSL"].price == pytest.approx(250.0)
    cached = service.get_cached(["CSL"])
    assert not cached["CSL"].stale
    repo.close()


def test_cache_ttl_and_stale_logic(tmp_path):
    tz = ZoneInfo("Australia/Brisbane")
    provider = DummyProvider(200.0, tz=tz)
    now = [aware(2024, 1, 1, 9, 0)]
    repo, service = _service(tmp_path, provider, now)
    service.refresh_prices(["CSL"])
    now[0] = now[0] + timedelta(minutes=61)
    cached = service.get_cached(["CSL"])
    assert cached["CSL"].stale is True
    repo.close()


def test_manual_override_preserved_during_refresh(tmp_path):
    tz = ZoneInfo("Australia/Brisbane")
    provider = DummyProvider(210.0, tz=tz)
    now = [aware(2024, 1, 1, 9, 0)]
    repo, service = _service(tmp_path, provider, now)
    service.refresh_prices(["CSL"])
    now[0] = now[0] + timedelta(minutes=1)
    service.set_manual("CSL", 305.5, aware(2024, 1, 1, 9, 1))
    provider.price = 190.0
    provider.asof = aware(2024, 1, 1, 9, 2)
    now[0] = now[0] + timedelta(minutes=1)
    service.refresh_prices(["CSL"])
    cached = service.get_cached(["CSL"])
    assert cached["CSL"].price == pytest.approx(305.5)
    repo.close()


def test_online_default_provider_parses_http_payload():
    captured = {}

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params

            class DummyResponse:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "quoteResponse": {
                            "result": [
                                {
                                    "symbol": "CSL.AX",
                                    "regularMarketPrice": 255.55,
                                    "regularMarketTime": 1700000000,
                                }
                            ]
                        }
                    }

            return DummyResponse()

    provider = OnlineDefaultProvider(client_factory=DummyClient)
    quotes = provider.fetch(["CSL.AX"])
    quote = quotes["CSL.AX"]
    assert quote.price == pytest.approx(255.55)
    assert captured["params"]["symbols"] == "CSL.AX"


def test_positions_without_prices_show_none(tmp_path):
    repo = JSONRepository(tmp_path / "positions.json")
    service = PortfolioService(repo)
    txn = Transaction(
        dt=aware(2024, 1, 1, 10, 0),
        type="BUY",
        symbol="CSL",
        qty=5.0,
        price=100.0,
        fees=0.0,
    )
    service.record_trade(txn)
    positions = service.compute_positions(prices={})
    assert positions[0].mv is None
    repo.close()
