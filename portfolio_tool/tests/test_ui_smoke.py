from __future__ import annotations

import datetime as dt

import pytest

textual = pytest.importorskip("textual")

from portfolio_tool.config import Config
from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.data.repo import Database

from ui.textual_app import PortfolioApp, PortfolioServices


class DummyProvider:
    def get_last(self, symbols):  # pragma: no cover - not exercised
        now = dt.datetime.now(dt.timezone.utc)
        return {
            symbol: PriceQuote(symbol=symbol, price=0, currency="USD", asof=now, provider="dummy")
            for symbol in symbols
        }


def test_portfolio_app_instantiation(tmp_path):
    cfg = Config()
    cfg.db_path = tmp_path / "test.db"
    db = Database(cfg)
    db.create_all()
    pricing = PriceService(cfg, DummyProvider())
    services = PortfolioServices(cfg, db, pricing)
    app = PortfolioApp(services)
    assert app.services is services
