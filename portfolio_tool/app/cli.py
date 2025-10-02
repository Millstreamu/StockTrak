"""Command-line interface for the portfolio tool."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import typer
from rich import print

from ..core.config import ensure_config, load_config
from ..core.pricing import PricingService
from ..data import JSONRepository, SQLiteRepository
from ..plugins.pricing import get_provider

DATA_DIR = Path("data")


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


# Ensure configuration is ready at import time to cover --help invocations.
ensure_config()

app = typer.Typer(help="Portfolio Tool — Terminal Edition")
prices_app = typer.Typer(help="Price cache management")
app.add_typer(prices_app, name="prices")


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


if __name__ == "__main__":
    sys.exit(app())
