"""Command-line interface for the portfolio tool."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

import typer
from rich import print
from rich.console import Console
from rich.table import Table
from zoneinfo import ZoneInfo

from ..core.config import ensure_config, load_config
from ..core.pricing import PricingService
from ..core.reports import ReportingService, set_reporting_engine
from ..core.rules import ActionableService
from ..core.services import PortfolioService
from ..data import JSONRepository, SQLiteRepository
from ..plugins.pricing import get_provider
from ..reports import csv_renderer, md_renderer

DATA_DIR = Path("data")
console = Console()


def _open_repository(config: dict) -> SQLiteRepository | JSONRepository:
    """Instantiate the configured repository backend."""

    storage_cfg = config.get("storage", {})
    backend = (storage_cfg.get("backend") or "sqlite").lower()
    DATA_DIR.mkdir(exist_ok=True)
    if backend == "sqlite":
        path = storage_cfg.get("path") or DATA_DIR / "portfolio.sqlite"
        return SQLiteRepository(Path(path))
    if backend == "json":
        path = storage_cfg.get("path") or DATA_DIR / "portfolio.json"
        return JSONRepository(Path(path))
    raise typer.BadParameter(f"Unsupported storage backend: {backend}")


def _known_symbols(repo: SQLiteRepository | JSONRepository) -> list[str]:
    """Return a sorted list of symbols referenced in transactions."""

    rows = repo.list_transactions()
    return sorted({row["symbol"] for row in rows})


def _build_pricing_service(repo, config: dict) -> PricingService:
    prices_cfg = config.get("prices", {})
    provider_name = prices_cfg.get("provider", "manual_inline")
    provider = get_provider(provider_name)
    timezone = config.get("timezone", "Australia/Brisbane")
    cache_ttl = prices_cfg.get("cache_ttl_minutes", 15)
    stale_max = prices_cfg.get("stale_price_max_minutes", 60)
    suffix_map = prices_cfg.get("exchange_suffix_map", {})
    return PricingService(
        repo,
        provider,
        cache_ttl_minutes=cache_ttl,
        stale_price_max_minutes=stale_max,
        timezone=timezone,
        exchange_suffix_map=suffix_map,
    )


def _portfolio_service(repo, config: dict) -> PortfolioService:
    timezone = config.get("timezone", "Australia/Brisbane")
    lot_method = config.get("lot_matching", "FIFO")
    brokerage = config.get("brokerage_allocation", "BUY")
    return PortfolioService(
        repo,
        timezone=timezone,
        lot_matching=lot_method,
        brokerage_allocation=brokerage,
    )


def _reporting_service(repo, config: dict, portfolio: PortfolioService) -> ReportingService:
    return ReportingService(
        repo,
        timezone=config.get("timezone", "Australia/Brisbane"),
        base_currency=config.get("base_currency", "AUD"),
        portfolio_service=portfolio,
    )


def _parse_asof_option(value: str | None, timezone: str) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo:
        return dt.astimezone(ZoneInfo(timezone))
    return datetime(dt.year, dt.month, dt.day, tzinfo=ZoneInfo(timezone))


def _format_console_value(value: object) -> str:
    if value is None:
        return "[dim]N/A[/dim]"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _render_table(rows: Sequence[dict[str, object]], columns: Sequence[tuple[str, str]]) -> None:
    table = Table(show_header=True, header_style="bold")
    for _, title in columns:
        table.add_column(title)
    for row in rows:
        table.add_row(*[_format_console_value(row.get(key)) for key, _ in columns])
    console.print(table)


def _handle_export(
    export: tuple[str, Path] | None,
    rows: Sequence[dict[str, object]],
    *,
    fieldnames: Sequence[str],
) -> None:
    if not export or not rows:
        return
    fmt_raw, target = export
    fmt = (fmt_raw or "").lower()
    if fmt == "csv":
        csv_renderer.write(rows, target, fieldnames)
    elif fmt == "md":
        md_renderer.write(rows, target, fieldnames)
    else:
        raise typer.BadParameter("Export format must be 'csv' or 'md'")
    print(f"[green]Exported report to {target}")


def _symbols_with_open_lots(repo) -> list[str]:
    rows = repo.list_lots(only_open=True)
    return sorted({row["symbol"] for row in rows})


def _actionable_rows(items: Sequence) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in items:
        rows.append(
            {
                "id": getattr(item, "id", None),
                "type": getattr(item, "type", None),
                "symbol": getattr(item, "symbol", None),
                "message": getattr(item, "message", None),
                "status": getattr(item, "status", None),
                "snoozed_until": getattr(item, "snoozed_until", None),
                "updated_at": getattr(item, "updated_at", None),
            }
        )
    return rows


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

POSITIONS_COLUMNS = [
    ("symbol", "Symbol"),
    ("quantity", "Qty"),
    ("avg_cost", "Avg Cost"),
    ("cost_base", "Cost Base"),
    ("price", "Price"),
    ("market_value", "Market Value"),
    ("weight_pct", "Weight %"),
    ("price_source", "Source"),
    ("price_asof", "Price As-of"),
    ("price_stale", "Stale"),
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

LOTS_COLUMNS = [
    ("lot_id", "Lot"),
    ("symbol", "Symbol"),
    ("acquired_at", "Acquired"),
    ("threshold_date", "CGT Threshold"),
    ("qty_remaining", "Qty Remaining"),
    ("cost_base_remaining", "Cost Base"),
    ("status", "Status"),
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

CGT_COLUMNS = [
    ("symbol", "Symbol"),
    ("lot_id", "Lot"),
    ("threshold_date", "Threshold"),
    ("days_until", "Days"),
    ("eligible_for_discount", "Eligible"),
    ("qty_remaining", "Qty"),
]

ACTIONABLE_FIELDS = [
    "id",
    "type",
    "symbol",
    "message",
    "status",
    "snoozed_until",
    "updated_at",
]

ACTIONABLE_COLUMNS = [
    ("id", "ID"),
    ("type", "Type"),
    ("symbol", "Symbol"),
    ("message", "Message"),
    ("status", "Status"),
    ("snoozed_until", "Snoozed"),
    ("updated_at", "Updated"),
]


# Ensure configuration is ready at import time to cover --help invocations.
ensure_config()

app = typer.Typer(help="Portfolio Tool — Terminal Edition")
prices_app = typer.Typer(help="Price cache management")
report_app = typer.Typer(help="Reporting commands")
app.add_typer(prices_app, name="prices")
app.add_typer(report_app, name="report")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> Optional[int]:
    """Application entrypoint that ensures configuration is present."""

    ensure_config()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        return 0
    return None


@app.command()
def version() -> None:
    """Print the CLI version."""

    print("portfolio-tool 0.0.1")


@app.command()
def positions(
    asof: Optional[str] = typer.Option(
        None,
        help="Report as-of date (YYYY-MM-DD or ISO timestamp).",
    ),
    refresh_prices: bool = typer.Option(
        False,
        "--refresh-prices",
        help="Fetch live prices before generating the report.",
    ),
    export: tuple[str, Path] | None = typer.Option(
        None,
        "--export",
        metavar="FORMAT PATH",
        help="Export the report to CSV or Markdown.",
    ),
) -> None:
    config = load_config()
    repo = _open_repository(config)
    tz_name = config.get("timezone", "Australia/Brisbane")
    try:
        portfolio = _portfolio_service(repo, config)
        reporting = _reporting_service(repo, config, portfolio)
        set_reporting_engine(reporting)
        pricing = _build_pricing_service(repo, config)
        asof_dt = _parse_asof_option(asof, tz_name) or datetime.now(tz=ZoneInfo(tz_name))
        symbols = _symbols_with_open_lots(repo)
        quotes = (
            pricing.refresh_prices(symbols or None)
            if refresh_prices
            else pricing.get_cached(symbols)
        )
        rows = reporting.positions_snapshot(asof_dt, quotes)
        if rows:
            _render_table(rows, POSITIONS_COLUMNS)
        else:
            print("[yellow]No open positions[/yellow]")
        _handle_export(export, rows, fieldnames=POSITIONS_FIELDS)
    finally:
        set_reporting_engine(None)
        repo.close()


@app.command()
def lots(
    symbol: Optional[str] = typer.Argument(
        None,
        help="Filter to a specific symbol.",
    ),
    export: tuple[str, Path] | None = typer.Option(
        None,
        "--export",
        metavar="FORMAT PATH",
        help="Export the report to CSV or Markdown.",
    ),
) -> None:
    config = load_config()
    repo = _open_repository(config)
    try:
        portfolio = _portfolio_service(repo, config)
        reporting = _reporting_service(repo, config, portfolio)
        rows = reporting.lots_ledger(symbol)
        if rows:
            _render_table(rows, LOTS_COLUMNS)
        else:
            print("[yellow]No lots found[/yellow]")
        _handle_export(export, rows, fieldnames=LOTS_FIELDS)
    finally:
        repo.close()


@app.command("cgt-calendar")
def cgt_calendar(
    window: int = typer.Option(
        60,
        "--window",
        help="Window (in days) to highlight upcoming CGT discount eligibility.",
        show_default=True,
    ),
    export: tuple[str, Path] | None = typer.Option(
        None,
        "--export",
        metavar="FORMAT PATH",
        help="Export the report to CSV or Markdown.",
    ),
) -> None:
    if window not in {30, 60, 90}:
        raise typer.BadParameter("Window must be one of 30, 60, or 90 days")
    config = load_config()
    repo = _open_repository(config)
    tz_name = config.get("timezone", "Australia/Brisbane")
    try:
        portfolio = _portfolio_service(repo, config)
        reporting = _reporting_service(repo, config, portfolio)
        asof_dt = datetime.now(tz=ZoneInfo(tz_name))
        rows = reporting.cgt_calendar(asof=asof_dt, window_days=window)
        if rows:
            _render_table(rows, CGT_COLUMNS)
        else:
            print("[yellow]No CGT events within window[/yellow]")
        _handle_export(export, rows, fieldnames=CGT_FIELDS)
    finally:
        repo.close()


@app.command()
def actionables(
    complete: Optional[int] = typer.Option(
        None,
        "--complete",
        metavar="ID",
        help="Mark an actionable as completed.",
    ),
    snooze: Optional[int] = typer.Option(
        None,
        "--snooze",
        metavar="ID",
        help="Snooze an actionable for a number of days.",
    ),
    days: Optional[int] = typer.Option(
        None,
        "--days",
        help="Days to snooze when using --snooze.",
    ),
) -> None:
    if complete is not None and snooze is not None:
        raise typer.BadParameter("Use either --complete or --snooze, not both")
    if snooze is not None and (days is None or days <= 0):
        raise typer.BadParameter("--days must be greater than zero when snoozing")
    config = load_config()
    repo = _open_repository(config)
    tz_name = config.get("timezone", "Australia/Brisbane")
    try:
        portfolio = _portfolio_service(repo, config)
        reporting = _reporting_service(repo, config, portfolio)
        pricing = _build_pricing_service(repo, config)
        service = ActionableService(
            repo,
            portfolio_service=portfolio,
            reporting_service=reporting,
            pricing_service=pricing,
            timezone=tz_name,
            target_weights=config.get("target_weights", {}),
            rule_thresholds=config.get("rule_thresholds", {}),
        )
        items = service.evaluate_rules(include_snoozed=True)
        message: str | None = None
        if complete is not None:
            service.complete(complete)
            message = f"Marked actionable {complete} complete"
            items = service.list_actionables(include_snoozed=True)
        elif snooze is not None and days is not None:
            service.snooze(snooze, days)
            message = f"Snoozed actionable {snooze} for {days} days"
            items = service.list_actionables(include_snoozed=True)
        if message:
            print(f"[green]{message}[/green]")
        active_items = [item for item in items if getattr(item, "status", "").upper() != "DONE"]
        rows = _actionable_rows(active_items)
        if rows:
            _render_table(rows, ACTIONABLE_COLUMNS)
        else:
            print("[yellow]No actionables[/yellow]")
    finally:
        repo.close()


@report_app.command("daily")
def report_daily(
    refresh_prices: bool = typer.Option(
        False,
        "--refresh-prices",
        help="Fetch live prices before reporting.",
    ),
    export: tuple[str, Path] | None = typer.Option(
        None,
        "--export",
        metavar="FORMAT PATH",
        help="Export the daily snapshot to CSV or Markdown.",
    ),
) -> None:
    config = load_config()
    repo = _open_repository(config)
    tz_name = config.get("timezone", "Australia/Brisbane")
    try:
        portfolio = _portfolio_service(repo, config)
        reporting = _reporting_service(repo, config, portfolio)
        set_reporting_engine(reporting)
        pricing = _build_pricing_service(repo, config)
        asof_dt = datetime.now(tz=ZoneInfo(tz_name))
        symbols = _symbols_with_open_lots(repo)
        quotes = (
            pricing.refresh_prices(symbols or None)
            if refresh_prices
            else pricing.get_cached(symbols)
        )
        rows = reporting.positions_snapshot(asof_dt, quotes)
        if rows:
            print(
                f"[bold]Daily snapshot {asof_dt.date()} (base {config.get('base_currency', 'AUD')})[/bold]"
            )
            _render_table(rows, POSITIONS_COLUMNS)
        else:
            print("[yellow]No positions to report[/yellow]")
        _handle_export(export, rows, fieldnames=POSITIONS_FIELDS)
    finally:
        set_reporting_engine(None)
        repo.close()


def _render_quotes(quotes: Iterable) -> None:
    if not quotes:
        print("[yellow]No price data available[/yellow]")
        return
    for quote in quotes:
        stale_flag = " (stale)" if quote.stale else ""
        print(
            f"[bold]{quote.symbol}[/bold]: {quote.price:.4f}"
            f" from {quote.source} @ {quote.asof.isoformat()}{stale_flag}"
        )


@prices_app.command("show")
def prices_show(symbols: list[str] = typer.Argument(None)) -> None:
    """Display cached price quotes for the requested symbols."""

    config = load_config()
    repo = _open_repository(config)
    try:
        service = _build_pricing_service(repo, config)
        targets = symbols or _known_symbols(repo)
        quotes = service.get_cached(targets)
        _render_quotes(quotes.values())
    finally:
        repo.close()


@prices_app.command("refresh")
def prices_refresh(symbols: list[str] = typer.Argument(None)) -> None:
    """Refresh live prices using the configured provider."""

    config = load_config()
    repo = _open_repository(config)
    try:
        service = _build_pricing_service(repo, config)
        targets = symbols or _known_symbols(repo)
        quotes = service.refresh_prices(targets or None)
        _render_quotes(quotes.values())
    finally:
        repo.close()


@prices_app.command("set")
def prices_set(
    symbol: str,
    price: float,
    asof: Optional[str] = typer.Option(
        None,
        help="ISO-8601 timestamp for the manual quote (defaults to now)",
    ),
) -> None:
    """Manually set or override a price quote."""

    config = load_config()
    repo = _open_repository(config)
    try:
        service = _build_pricing_service(repo, config)
        asof_dt = datetime.fromisoformat(asof) if asof else None
        quotes = service.set_manual(symbol, price, asof_dt)
        _render_quotes(quotes.values())
    finally:
        repo.close()


@app.command()
def tui() -> None:
    """Launch the Textual TUI."""

    ensure_config()
    from .tui import PortfolioApp

    PortfolioApp().run()


if __name__ == "__main__":
    sys.exit(app())
