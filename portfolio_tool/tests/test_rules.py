from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.core.reports import build_positions
from portfolio_tool.core.rules import generate_all_actionables
from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models


class MappingProvider:
    def __init__(self, prices: dict[str, Decimal]):
        self.prices = prices

    def get_last(self, symbols: list[str]) -> dict[str, PriceQuote]:
        now = dt.datetime.now(dt.timezone.utc)
        return {
            symbol: PriceQuote(
                symbol=symbol,
                price=self.prices[symbol],
                currency="AUD",
                asof=now,
                provider="mapping",
            )
            for symbol in symbols
        }


def test_actionables_cover_rules(cfg, db):
    cfg.target_weights = {"AAA": 0.2, "BBB": 0.1}
    cfg.rule_thresholds.cgt_window_days = 120
    cfg.rule_thresholds.overweight_band = 0.01
    cfg.rule_thresholds.concentration_limit = 0.3
    cfg.rule_thresholds.drawdown_pct = 0.1
    cfg.rule_thresholds.stale_note_days = 30

    provider = MappingProvider({"AAA": Decimal("20"), "BBB": Decimal("5")})
    service = PriceService(cfg, provider)

    with db.session_scope() as session:
        old_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=350)
        recent_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)
        record_trade(
            session,
            cfg,
            TradeInput(
                side="BUY",
                symbol="AAA",
                dt=old_dt,
                qty=Decimal("10"),
                price=Decimal("10"),
                fees=Decimal("0"),
                note="Long term",
            ),
        )
        record_trade(
            session,
            cfg,
            TradeInput(
                side="BUY",
                symbol="BBB",
                dt=recent_dt,
                qty=Decimal("10"),
                price=Decimal("10"),
                fees=Decimal("0"),
            ),
        )
        # Force note to appear stale
        trade = session.scalars(select(models.Trade).where(models.Trade.symbol == "AAA")).first()
        trade.updated_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=120)
        positions = build_positions(session, cfg, service)
        lots = list(session.scalars(select(models.Lot)))
        actionables = generate_all_actionables(session, cfg, positions, lots)
        types = {a.type for a in actionables}
        assert {"cgt_window", "overweight", "concentration", "drawdown", "stale_note"} <= types
