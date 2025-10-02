from __future__ import annotations

from datetime import datetime
from pathlib import Path

from zoneinfo import ZoneInfo

from portfolio_tool.core.models import PriceQuote, Transaction
from portfolio_tool.core.reports import ReportingService
from portfolio_tool.core.services import PortfolioService
from portfolio_tool.data.repo_json import JSONRepository
from portfolio_tool.reports import csv_renderer, md_renderer


GOLDEN_DIR = Path(__file__).parent / "golden"

POSITIONS_FIELDS = [
    "report_asof",
    "base_currency",
    "symbol",
    "quantity",
    "avg_cost",
    "cost_base",
    "price",
    "market_value",
    "weight_pct",
    "price_source",
    "price_asof",
    "price_stale",
]

LOTS_FIELDS = [
    "lot_id",
    "symbol",
    "acquired_at",
    "threshold_date",
    "original_qty",
    "qty_remaining",
    "qty_disposed",
    "cost_base_initial",
    "cost_base_remaining",
    "status",
    "source_txn_id",
]

CGT_FIELDS = [
    "report_asof",
    "window_days",
    "symbol",
    "lot_id",
    "acquired_at",
    "threshold_date",
    "days_until",
    "eligible_for_discount",
    "qty_remaining",
]


def aware(year, month, day, hour=0, minute=0):
    tz = ZoneInfo("Australia/Brisbane")
    return datetime(year, month, day, hour, minute, tzinfo=tz)


def build_sample(tmp_path):
    repo = JSONRepository(tmp_path / "sample.json")
    portfolio = PortfolioService(repo)

    portfolio.record_trade(
        Transaction(
            dt=aware(2023, 7, 1, 10, 0),
            type="BUY",
            symbol="CSL",
            qty=100,
            price=240.0,
            fees=9.95,
            exchange="ASX",
        )
    )
    portfolio.record_trade(
        Transaction(
            dt=aware(2023, 9, 15, 11, 0),
            type="BUY",
            symbol="IOZ",
            qty=200,
            price=30.0,
            fees=12.50,
            exchange="ASX",
        )
    )
    portfolio.record_trade(
        Transaction(
            dt=aware(2024, 2, 1, 10, 30),
            type="SELL",
            symbol="CSL",
            qty=40,
            price=260.0,
            fees=9.95,
            exchange="ASX",
        )
    )
    portfolio.record_trade(
        Transaction(
            dt=aware(2024, 3, 10, 9, 30),
            type="BUY",
            symbol="CSL",
            qty=50,
            price=250.0,
            fees=8.00,
            exchange="ASX",
        )
    )

    reporting = ReportingService(
        repo,
        timezone="Australia/Brisbane",
        base_currency="AUD",
        portfolio_service=portfolio,
    )
    asof = aware(2024, 6, 20, 12, 0)
    quotes = {
        "CSL": PriceQuote(
            symbol="CSL",
            asof=aware(2024, 6, 20, 10, 0),
            price=255.45,
            source="manual",
            stale=False,
        ),
        "IOZ": PriceQuote(
            symbol="IOZ",
            asof=aware(2024, 6, 20, 11, 0),
            price=31.2,
            source="manual",
            stale=False,
        ),
    }

    positions = reporting.positions_snapshot(asof, quotes)
    lots = reporting.lots_ledger()
    cgt = reporting.cgt_calendar(asof=asof, window_days=60)
    return positions, lots, cgt


def test_positions_report_matches_golden(tmp_path):
    positions, _, _ = build_sample(tmp_path)
    csv_text = csv_renderer.render(positions, POSITIONS_FIELDS)
    md_text = md_renderer.render(positions, POSITIONS_FIELDS)
    assert csv_text == (GOLDEN_DIR / "positions_snapshot.csv").read_text()
    assert md_text == (GOLDEN_DIR / "positions_snapshot.md").read_text()


def test_lots_report_matches_golden(tmp_path):
    _, lots, _ = build_sample(tmp_path)
    csv_text = csv_renderer.render(lots, LOTS_FIELDS)
    md_text = md_renderer.render(lots, LOTS_FIELDS)
    assert csv_text == (GOLDEN_DIR / "lots_ledger.csv").read_text()
    assert md_text == (GOLDEN_DIR / "lots_ledger.md").read_text()


def test_cgt_calendar_matches_golden(tmp_path):
    _, _, cgt = build_sample(tmp_path)
    csv_text = csv_renderer.render(cgt, CGT_FIELDS)
    md_text = md_renderer.render(cgt, CGT_FIELDS)
    assert csv_text == (GOLDEN_DIR / "cgt_calendar.csv").read_text()
    assert md_text == (GOLDEN_DIR / "cgt_calendar.md").read_text()
