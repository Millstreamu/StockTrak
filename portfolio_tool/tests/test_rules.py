from __future__ import annotations

from datetime import datetime, timedelta

from zoneinfo import ZoneInfo

from portfolio_tool.core.models import Transaction
from portfolio_tool.core.pricing import PricingService
from portfolio_tool.core.reports import ReportingService
from portfolio_tool.core.rules import ActionableService
from portfolio_tool.core.services import PortfolioService
from portfolio_tool.data.repo_json import JSONRepository
from portfolio_tool.plugins.pricing.manual_inline import ManualInlineProvider


TZ = ZoneInfo("Australia/Brisbane")


def aware(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=TZ)


def build_service(tmp_path):
    repo = JSONRepository(tmp_path / "repo.json")
    portfolio = PortfolioService(repo, timezone="Australia/Brisbane")
    portfolio.record_trade(
        Transaction(
            dt=aware(2023, 1, 1, 10, 0),
            type="BUY",
            symbol="CSL",
            qty=100,
            price=200.0,
            fees=9.95,
            notes="init position",
        )
    )
    portfolio.record_trade(
        Transaction(
            dt=aware(2023, 7, 1, 9, 30),
            type="BUY",
            symbol="IOZ",
            qty=200,
            price=30.0,
            fees=10.0,
            notes="stop 25",
        )
    )
    current_time = [aware(2024, 6, 10, 12, 0)]
    provider = ManualInlineProvider(timezone="Australia/Brisbane")
    pricing = PricingService(
        repo,
        provider,
        cache_ttl_minutes=60,
        stale_price_max_minutes=60,
        timezone="Australia/Brisbane",
        now_fn=lambda: current_time[0],
    )
    reporting = ReportingService(
        repo,
        timezone="Australia/Brisbane",
        base_currency="AUD",
        portfolio_service=portfolio,
    )
    service = ActionableService(
        repo,
        portfolio_service=portfolio,
        reporting_service=reporting,
        pricing_service=pricing,
        timezone="Australia/Brisbane",
        target_weights={"CSL": 0.4, "IOZ": 0.6},
        rule_thresholds={
            "cgt_window_days": 30,
            "overweight_band": 0.05,
            "concentration_limit": 0.5,
            "loss_threshold_pct": -0.15,
        },
        now_fn=lambda: current_time[0],
    )
    pricing.set_manual("CSL", 150.0, aware(2024, 6, 10, 9, 0))
    pricing.set_manual("IOZ", 31.0, aware(2024, 3, 1, 9, 0))
    repo.upsert_price(
        {
            "symbol": "IOZ",
            "asof": aware(2024, 3, 1, 9, 0).isoformat(),
            "price": 31.0,
            "source": "manual",
            "fetched_at": aware(2024, 3, 1, 9, 30).isoformat(),
            "stale": 1,
        }
    )
    return service, repo, current_time


def test_rules_generate_expected_actionables(tmp_path):
    service, repo, _ = build_service(tmp_path)
    try:
        items = service.evaluate_rules(include_snoozed=True)
        types = {(item.type, item.symbol) for item in items}
        assert ("OVERWEIGHT", "CSL") in types
        assert ("CONCENTRATION", "CSL") in types
        assert ("UNREALISED_LOSS", "CSL") in types
        assert ("TRAILING_STOP", "CSL") in types
        assert ("UNDERWEIGHT", "IOZ") in types
        assert any(item.type == "CGT_WINDOW" and item.symbol == "IOZ" for item in items)
        assert any(item.type == "STALE_PRICE" and item.symbol == "IOZ" for item in items)
        assert not any(item.type == "TRAILING_STOP" and item.symbol == "IOZ" for item in items)
    finally:
        repo.close()


def test_actionable_lifecycle_complete_and_snooze(tmp_path):
    service, repo, current_time = build_service(tmp_path)
    try:
        items = service.evaluate_rules(include_snoozed=True)
        overweight = next(item for item in items if item.type == "OVERWEIGHT")
        service.complete(overweight.id)
        done_items = service.list_actionables(status="DONE")
        assert any(item.id == overweight.id for item in done_items)

        reopened = service.evaluate_rules(include_snoozed=True)
        reopened_overweight = next(item for item in reopened if item.id == overweight.id)
        assert reopened_overweight.status == "OPEN"

        stale_item = next(item for item in reopened if item.type == "STALE_PRICE")
        service.snooze(stale_item.id, 2)
        snoozed_list = service.list_actionables(include_snoozed=True)
        snoozed_item = next(item for item in snoozed_list if item.id == stale_item.id)
        assert snoozed_item.status == "SNOOZE"
        assert snoozed_item.snoozed_until is not None

        current_time[0] = current_time[0] + timedelta(days=3)
        reopened_again = service.evaluate_rules(include_snoozed=True)
        reopened_stale = next(item for item in reopened_again if item.id == stale_item.id)
        assert reopened_stale.status == "OPEN"
        assert reopened_stale.snoozed_until is None
    finally:
        repo.close()
