from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.core.reports import build_positions
from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.reports.md_renderer import positions_markdown


class StaticProvider:
    def get_last(self, symbols: list[str]):
        now = dt.datetime.now(dt.timezone.utc)
        return {
            symbol: PriceQuote(
                symbol=symbol,
                price=Decimal("12"),
                currency="AUD",
                asof=now,
                provider="static",
            )
            for symbol in symbols
        }


def test_positions_markdown_golden(cfg, db):
    provider = StaticProvider()
    service = PriceService(cfg, provider)
    base_dt = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with db.session_scope() as session:
        record_trade(
            session,
            cfg,
            TradeInput(
                side="BUY",
                symbol="AAA",
                dt=base_dt,
                qty=Decimal("10"),
                price=Decimal("10"),
                fees=Decimal("5"),
            ),
        )
        positions = build_positions(session, cfg, service)
        md = positions_markdown(positions)
    golden = Path(__file__).parent / "golden" / "positions.md"
    assert md.strip() == golden.read_text(encoding="utf-8").strip()
