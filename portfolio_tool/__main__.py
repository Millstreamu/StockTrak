from __future__ import annotations

import datetime as dt
import sys
import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Optional

import typer
from zoneinfo import ZoneInfo

try:  # pragma: no cover - exercised implicitly when Rich is available
    from rich.console import Console  # type: ignore
    from rich.table import Table  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    class Table:  # type: ignore[override]
        """Minimal fallback table renderer when Rich is unavailable."""

        def __init__(self, title: str | None = None):
            self.title = title
            self._columns: list[str] = []
            self._rows: list[tuple[str, ...]] = []

        def add_column(self, header: str, **_: object) -> None:
            self._columns.append(str(header))

        def add_row(self, *values: object, **_: object) -> None:
            padded = tuple(str(value) for value in values)
            self._rows.append(padded)

        def _render(self) -> str:
            if not self._columns:
                return ""
            all_rows = [self._columns, *[list(row) for row in self._rows]]
            widths = [max(len(row[idx]) for row in all_rows) for idx in range(len(self._columns))]

            def format_row(row: list[str]) -> str:
                padded = [row[idx].ljust(widths[idx]) for idx in range(len(self._columns))]
                return " | ".join(padded)

            lines: list[str] = []
            if self.title:
                lines.append(self.title)
            lines.append(format_row(self._columns))
            lines.append("-+-".join("-" * width for width in widths))
            for row in self._rows:
                lines.append(format_row(list(row)))
            return "\n".join(lines)

    class Console:  # type: ignore[override]
        """Simplified console that mirrors the subset of Rich used in tests."""

        @staticmethod
        def _strip_markup(text: str) -> str:
            return text.replace("[", "").replace("]", "")

        def print(self, *objects: object, sep: str = " ", end: str = "\n") -> None:
            rendered: list[str] = []
            for obj in objects:
                if isinstance(obj, Table):
                    rendered.append(obj._render())
                else:
                    rendered.append(self._strip_markup(str(obj)))
            print(sep.join(rendered), end=end)

from portfolio_tool.config import Config, load_config
from portfolio_tool.core.cgt import cgt_threshold
from portfolio_tool.core.diagnostics import collect_diagnostics, determine_price_status
from portfolio_tool.core.lots import apply_disposal, match_disposal
from portfolio_tool.core.pricing import PriceService
from portfolio_tool.core.reports import (
    build_audit_log,
    build_cgt_calendar,
    build_lots,
    build_positions,
    build_pnl,
)
from portfolio_tool.core.rules import generate_all_actionables
from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models, repo
from portfolio_tool.data.init_db import ensure_db
from portfolio_tool.data.repo import Database
from portfolio_tool.providers.fallback_provider import FallbackPriceProvider
from ui.textual_app import PortfolioApp, PortfolioServices, build_services
from portfolio_tool.reports import md_renderer, tables
from sqlalchemy import select

console = Console()
app = typer.Typer(help="Portfolio tracker")
config_app = typer.Typer(help="Manage configuration")
app.add_typer(config_app, name="config")


def get_provider(cfg: Config):
    return FallbackPriceProvider(cfg)


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config.toml"),
):
    cfg = load_config(config)
    engine = ensure_db()
    database = Database(engine)
    ctx.obj = {"cfg": cfg, "db": database, "pricing": PriceService(cfg, get_provider(cfg))}


def _prompt_decimal(prompt: str, default: Optional[Decimal] = None) -> Decimal:
    default_str = str(default) if default is not None else None
    value = typer.prompt(prompt, default=default_str)
    return Decimal(value)


def _prompt_datetime(prompt: str, cfg: Config, default: Optional[dt.datetime] = None) -> dt.datetime:
    if default is None:
        default = dt.datetime.now(ZoneInfo(cfg.timezone))
    value = typer.prompt(prompt, default=default.isoformat())
    dt_value = dt.datetime.fromisoformat(value)
    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=ZoneInfo(cfg.timezone))
    return dt_value.astimezone(dt.timezone.utc)


@app.command()
def add_trade(
    ctx: typer.Context,
    side: Optional[str] = typer.Option(None, help="BUY or SELL"),
    symbol: Optional[str] = typer.Option(None, help="Ticker symbol"),
    method: Optional[str] = typer.Option(None, help="Lot matching override"),
):
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    if side is None:
        side = typer.prompt("Side (BUY/SELL)")
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise typer.BadParameter("Side must be BUY or SELL")
    if symbol is None:
        symbol = typer.prompt("Symbol").upper()
    else:
        symbol = symbol.upper()
    trade_dt = _prompt_datetime("Trade datetime (ISO)", cfg)
    qty = _prompt_decimal("Quantity")
    price = _prompt_decimal("Price")
    fees = _prompt_decimal("Fees", Decimal("0"))
    exchange = typer.prompt("Exchange", default="") or None
    note = typer.prompt("Note", default="") or None

    match_method = (method or cfg.lot_matching).upper()
    specific_ids = None
    if side == "SELL" and match_method == "SPECIFIC_ID":
        with db.session_scope() as session:
            lots = repo.list_open_lots(session, symbol)
        if not lots:
            raise typer.BadParameter("No lots available to match SELL")
        default_ids = ",".join(str(l.id) for l in lots)
        id_input = typer.prompt("Lot IDs (comma separated)", default=default_ids)
        specific_ids = [int(part.strip()) for part in id_input.split(",") if part.strip()]

    trade_input = TradeInput(
        side=side,
        symbol=symbol,
        dt=trade_dt,
        qty=qty,
        price=price,
        fees=fees,
        exchange=exchange,
        note=note,
    )

    try:
        with db.session_scope() as session:
            trade = record_trade(
                session,
                cfg,
                trade_input,
                match_method=match_method,
                specific_ids=specific_ids,
            )
        console.print(f"Created {side} trade {trade.id} for {symbol}")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def edit_trade(ctx: typer.Context, trade_id: int):
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        trade = session.get(models.Trade, trade_id)
        if not trade:
            raise typer.BadParameter("Trade not found")
        note = typer.prompt("Note", default=trade.note or "")
        updates = {"note": note}
        repo.update_trade(session, trade_id, updates)
        console.print(f"Updated trade {trade_id}")


@app.command()
def delete_trade(ctx: typer.Context, trade_id: int):
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        repo.delete_trade(session, trade_id)
        console.print(f"Deleted trade {trade_id}")


@app.command()
def positions(
    ctx: typer.Context,
    export_md: Optional[Path] = typer.Option(None, "--export", help="Export markdown path"),
):
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    pricing: PriceService = ctx.obj["pricing"]
    with db.session_scope() as session:
        rows = build_positions(session, cfg, pricing)
        table = tables.positions_table(rows)
        console.print(table)
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(md_renderer.positions_markdown(rows), encoding="utf-8")
            console.print(f"Exported markdown to {export_md}")


@app.command()
def lots(
    ctx: typer.Context,
    symbol: str,
    export_md: Optional[Path] = typer.Option(None, "--export", help="Export markdown path"),
):
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        rows = build_lots(session, symbol)
        table = tables.lots_table(rows)
        console.print(table)
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(md_renderer.lots_markdown(rows), encoding="utf-8")
            console.print(f"Exported markdown to {export_md}")


@app.command()
def cgt_calendar(
    ctx: typer.Context,
    window: Optional[int] = typer.Option(None, "--window", help="Days window"),
    export_md: Optional[Path] = typer.Option(None, "--export", help="Export markdown path"),
):
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    horizon = window or cfg.rule_thresholds.cgt_window_days
    with db.session_scope() as session:
        rows = build_cgt_calendar(session, cfg, horizon)
        table = tables.lots_table(rows)
        table.title = "CGT Calendar"
        console.print(table)
        if export_md:
            export_md.parent.mkdir(parents=True, exist_ok=True)
            export_md.write_text(md_renderer.lots_markdown(rows), encoding="utf-8")
            console.print(f"Exported markdown to {export_md}")


@app.command()
def pnl(
    ctx: typer.Context,
    realised: bool = typer.Option(False, "--realised", help="Show realised PnL"),
    unrealised: bool = typer.Option(False, "--unrealised", help="Show unrealised PnL"),
):
    if realised and unrealised:
        raise typer.BadParameter("Choose either realised or unrealised")
    realised = realised or not unrealised
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        rows = build_pnl(session, realised=realised)
        table = Table(title="Realised PnL" if realised else "Unrealised PnL")
        if realised:
            table.add_column("Symbol")
            table.add_column("Lot ID")
            table.add_column("Qty")
            table.add_column("Gain/Loss")
            table.add_column("Discount Eligible")
            for row in rows:
                table.add_row(
                    row["symbol"],
                    str(row["lot_id"]),
                    f"{row['qty']:.4f}",
                    f"{row['gain_loss']:.2f}",
                    "Yes" if row["eligible_discount"] else "No",
                )
        else:
            table.add_column("Symbol")
            table.add_column("Lot ID")
            table.add_column("Qty")
            table.add_column("Cost Base")
            table.add_column("CGT Threshold")
            for row in rows:
                table.add_row(
                    row["symbol"],
                    str(row["lot_id"]),
                    f"{row['qty']:.4f}",
                    f"{row['cost_base']:.2f}",
                    row["threshold_date"].isoformat(),
                )
        console.print(table)


@app.command()
def audit(ctx: typer.Context):
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        rows = build_audit_log(session)
        table = Table(title="Audit Log")
        table.add_column("ID")
        table.add_column("Action")
        table.add_column("Entity")
        table.add_column("Entity ID")
        table.add_column("Timestamp")
        table.add_column("Payload")
        for row in rows:
            table.add_row(
                str(row["id"]),
                row["action"],
                row["entity"],
                str(row["entity_id"]),
                row["created_at"].isoformat() if row["created_at"] else "",
                row["payload"] or "",
            )
        console.print(table)


@app.command()
def status(ctx: typer.Context):
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        diagnostics = collect_diagnostics(cfg, session)
    asof, reason = determine_price_status(diagnostics)
    table = Table(title="Portfolio Status")
    table.add_column("Metric")
    table.add_column("Value", overflow="fold")
    table.add_row("Python", sys.executable)
    table.add_row("DB Path", str(diagnostics.db_path))
    table.add_row("DB Exists", "Yes" if diagnostics.db_exists else "No")
    table.add_row("Trades", str(diagnostics.trade_count))
    table.add_row("Lots", str(diagnostics.lot_count))
    table.add_row("Prices", str(diagnostics.price_count))
    table.add_row("Actionables", str(diagnostics.actionable_count))
    latest = diagnostics.latest_price
    if latest:
        latest_asof = latest.asof.isoformat() if latest.asof else "—"
        table.add_row("Latest Price", f"{latest.symbol} @ {latest_asof}")
        table.add_row("Latest Price Stale", "Yes" if latest.is_stale else "No")
    else:
        table.add_row("Latest Price", "—")
        table.add_row("Latest Price Stale", "—")
    table.add_row("Price Status", reason)
    table.add_row("Price Status As Of", asof.isoformat() if asof else "—")
    table.add_row("Offline Mode", "Yes" if diagnostics.offline_mode else "No")
    table.add_row("Price Provider", diagnostics.price_provider)
    table.add_row("Price TTL Minutes", str(diagnostics.price_ttl_minutes))
    console.print(table)


@app.command()
def price_refresh(ctx: typer.Context, symbols: list[str]):
    if not symbols:
        raise typer.BadParameter("Provide at least one symbol")
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    pricing: PriceService = ctx.obj["pricing"]
    symbol_list = [s.upper() for s in symbols]
    if cfg.offline_mode:
        console.print("[yellow]offline_mode is true; cached prices will be used.[/yellow]")
    with db.session_scope() as session:
        quotes = pricing.get_quotes(session, symbol_list)
    table = Table(title="Price Refresh")
    table.add_column("Symbol")
    table.add_column("Price")
    table.add_column("Currency")
    table.add_column("As of")
    table.add_column("Provider")
    table.add_column("Status")
    for symbol in symbol_list:
        quote = quotes.get(symbol)
        if quote:
            table.add_row(
                quote.symbol,
                f"{quote.price:.2f}",
                quote.currency,
                quote.asof.isoformat(),
                quote.provider,
                "updated",
            )
        else:
            status = "offline_mode" if cfg.offline_mode else "no data"
            table.add_row(symbol, "—", "—", "—", "—", status)
    console.print(table)


@app.command()
def actionables(
    ctx: typer.Context,
    complete: Optional[int] = typer.Option(None, "--complete", help="Complete actionable ID"),
    snooze: Optional[int] = typer.Option(None, "--snooze", help="Snooze actionable ID"),
    days: int = typer.Option(7, help="Snooze days"),
):
    cfg: Config = ctx.obj["cfg"]
    db: Database = ctx.obj["db"]
    with db.session_scope() as session:
        if complete:
            actionable = session.get(models.Actionable, complete)
            if not actionable:
                raise typer.BadParameter("Actionable not found")
            actionable.status = "completed"
            console.print(f"Completed actionable {complete}")
            return
        if snooze:
            actionable = session.get(models.Actionable, snooze)
            if not actionable:
                raise typer.BadParameter("Actionable not found")
            actionable.due_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)
            console.print(f"Snoozed actionable {snooze} for {days} days")
            return
        positions_rows = build_positions(session, cfg, ctx.obj["pricing"])
        all_lots = session.scalars(select(models.Lot)).all()
        generated = generate_all_actionables(session, cfg, positions_rows, all_lots)
        existing = repo.list_actionables(session)
        existing_keys = {(a.type, a.message) for a in existing}
        for item in generated:
            key = (item.type, item.message)
            if key not in existing_keys:
                repo.create_actionable(
                    session,
                    type=item.type,
                    symbol=item.symbol,
                    message=item.message,
                    status="open",
                    due_at=item.due_at,
                )
        session.flush()
        open_items = repo.list_actionables(session)
        table = Table(title="Actionables")
        table.add_column("ID")
        table.add_column("Type")
        table.add_column("Symbol")
        table.add_column("Message")
        table.add_column("Due")
        table.add_column("Status")
        for item in open_items:
            table.add_row(
                str(item.id),
                item.type,
                item.symbol or "",
                item.message,
                item.due_at.isoformat() if item.due_at else "",
                item.status,
            )
        console.print(table)


@app.command()
def ui(
    ctx: typer.Context,
    demo: bool = typer.Option(False, "--demo", help="Launch demo environment"),
):
    cfg: Config = ctx.obj["cfg"]
    if demo:
        services = build_services(cfg, demo=True)
    else:
        db: Database = ctx.obj["db"]
        pricing: PriceService = ctx.obj["pricing"]
        services = PortfolioServices(cfg, db, pricing)
    PortfolioApp(services, demo=demo).run()


def _load_config_raw(path: Path) -> dict:
    if path.exists():
        with path.open("rb") as fh:
            return tomllib.load(fh)
    return {}


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    return f'"{value}"'


def _dump_toml(data: dict, prefix: Optional[str] = None) -> list[str]:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            continue
        lines.append(f"{key} = {_format_toml_value(value)}")
    for key, value in data.items():
        if isinstance(value, dict):
            section = key if prefix is None else f"{prefix}.{key}"
            lines.append(f"[{section}]")
            lines.extend(_dump_toml(value, section))
    return lines


def _set_config_value(data: dict, key: str, value: object) -> None:
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _parse_value(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        try:
            return Decimal(value)
        except Exception:
            return value


@config_app.command("show")
def config_show(ctx: typer.Context):
    console.print(ctx.obj["cfg"])


@config_app.command("set")
def config_set(ctx: typer.Context, key: str, value: str):
    cfg: Config = ctx.obj["cfg"]
    config_path = cfg.config_dir / "config.toml"
    cfg.config_dir.mkdir(parents=True, exist_ok=True)
    data = _load_config_raw(config_path)
    _set_config_value(data, key, _parse_value(value))
    lines = _dump_toml(data)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"Updated {config_path}")


if __name__ == "__main__":
    app()
