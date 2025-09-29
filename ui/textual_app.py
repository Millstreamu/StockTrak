from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Optional

from sqlalchemy import select

from portfolio_tool.config import Config, ensure_app_dirs, load_config
from portfolio_tool.core.pricing import PriceQuote, PriceService
from portfolio_tool.core.reports import (
    LotRow,
    PositionRow,
    build_cgt_calendar,
    build_lots,
    build_positions,
)
from portfolio_tool.core.rules import generate_all_actionables
from portfolio_tool.core.trades import TradeInput, record_trade
from portfolio_tool.data import models, repo
from portfolio_tool.data.repo import Database
from portfolio_tool.providers.fallback_provider import FallbackPriceProvider

try:  # pragma: no cover - exercised indirectly via textual UI usage
    from rich.table import Table
    from textual import events
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widget import Widget
    from textual.widgets import Button, Footer, Input, Label
    from textual.screen import ModalScreen
except ModuleNotFoundError as exc:  # pragma: no cover - textual optional for tests
    TEXTUAL_AVAILABLE = False
    _TEXTUAL_IMPORT_ERROR = exc
    if TYPE_CHECKING:  # pragma: no cover - typing only
        from textual import events  # type: ignore
        from textual.app import App, ComposeResult  # type: ignore
        from textual.containers import Container, Horizontal  # type: ignore
        from textual.widget import Widget  # type: ignore
        from textual.widgets import Button, Footer, Input, Label  # type: ignore
        from textual.screen import ModalScreen  # type: ignore
else:
    TEXTUAL_AVAILABLE = True

from .views.actionables import ActionableAction, ActionablesView
from .views.cgt_calendar import CGTCalendarView
from .views.dashboard import DashboardView
from .views.lots import LotSelected, LotsView
from .views.positions import PositionSelected, PositionsView
from .widgets.add_trade_modal import AddTradeModal
from .widgets.header import HeaderWidget
from .widgets.lot_detail import LotDetailWidget
from .widgets.sidebar import Sidebar
from .widgets.symbol_detail import SymbolDetailWidget
from .widgets.toasts import ToastManager


@dataclass
class PriceStatus:
    asof: Optional[dt.datetime]
    stale: bool


@dataclass
class DashboardSummary:
    total_value: Decimal
    cash: Decimal | None
    day_pl: Decimal | None
    top_weights: list[dict]
    upcoming_cgt: list[LotRow]
    actionable_count: int

class PortfolioServices:
    """Adapter layer for the TUI to interact with the domain services."""

    def __init__(self, cfg: Config, db: Database, pricing: PriceService):
        self.cfg = cfg
        self.db = db
        self.pricing = pricing

    def _session(self):
        return self.db.session_scope()

    def get_positions(self) -> list[PositionRow]:
        with self._session() as session:
            return build_positions(session, self.cfg, self.pricing)

    def get_lots(self, symbol: str | None = None) -> list[LotRow]:
        with self._session() as session:
            if symbol:
                return build_lots(session, symbol)
            stmt = (
                select(models.Lot)
                .where(models.Lot.qty_remaining > 0)
                .order_by(models.Lot.acquired_at)
            )
            lots: list[LotRow] = []
            for lot in session.scalars(stmt):
                lots.append(
                    LotRow(
                        lot_id=lot.id,
                        symbol=lot.symbol,
                        acquired_at=lot.acquired_at,
                        qty_remaining=Decimal(lot.qty_remaining),
                        cost_base=Decimal(lot.cost_base_total),
                        threshold_date=lot.threshold_date,
                    )
                )
            return lots

    def get_cgt_calendar(self, days: int) -> list[LotRow]:
        with self._session() as session:
            return build_cgt_calendar(session, self.cfg, days)

    def get_actionables(self) -> list[models.Actionable]:
        with self._session() as session:
            rows = repo.list_actionables(session)
            if rows:
                return rows
            positions = build_positions(session, self.cfg, self.pricing)
            lots = list(session.scalars(select(models.Lot)))
            generated = generate_all_actionables(session, self.cfg, positions, lots)
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
            return repo.list_actionables(session)

    def mark_actionable_done(self, actionable_id: int) -> None:
        with self._session() as session:
            actionable = session.get(models.Actionable, actionable_id)
            if actionable:
                actionable.status = "completed"

    def snooze_actionable(self, actionable_id: int, days: int) -> None:
        with self._session() as session:
            actionable = session.get(models.Actionable, actionable_id)
            if actionable:
                actionable.due_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)

    def get_symbol_detail(self, symbol: str) -> dict:
        with self._session() as session:
            lots = build_lots(session, symbol)
            trades_stmt = (
                select(models.Trade)
                .where(models.Trade.symbol == symbol.upper())
                .order_by(models.Trade.dt.desc())
                .limit(10)
            )
            trades = list(session.scalars(trades_stmt))
            price = repo.get_price(session, symbol.upper())
            return {
                "symbol": symbol.upper(),
                "lots": lots,
                "trades": trades,
                "price": price,
            }

    def get_lot_detail(self, lot_id: int) -> dict | None:
        with self._session() as session:
            lot = session.get(models.Lot, lot_id)
            if not lot:
                return None
            return {
                "lot": lot,
                "trade": lot.trade,
            }

    def get_price_status(self) -> PriceStatus:
        with self._session() as session:
            stmt = select(models.PriceCache).order_by(models.PriceCache.asof.desc())
            row = session.execute(stmt.limit(1)).scalars().first()
            if row:
                return PriceStatus(
                    asof=row.asof,
                    stale=bool(getattr(row, "is_stale", False)),
                )
            return PriceStatus(asof=None, stale=True)

    def refresh_prices(self, symbols: Iterable[str]) -> dict[str, PriceQuote]:
        with self._session() as session:
            return self.pricing.get_quotes(session, list(symbols))

    def record_trade(self, trade_input: TradeInput, match_method: str | None = None) -> None:
        with self._session() as session:
            record_trade(session, self.cfg, trade_input, match_method=match_method)

    def dashboard_summary(self) -> DashboardSummary:
        positions = self.get_positions()
        total_value = Decimal("0")
        top_weights: list[tuple[str, Decimal]] = []
        for row in positions:
            if row.market_value is not None:
                total_value += Decimal(row.market_value)
            if row.weight is not None:
                top_weights.append((row.symbol, Decimal(row.weight)))
        top_weights.sort(key=lambda item: item[1], reverse=True)
        top_rows = [
            {"symbol": sym, "weight": float(weight)} for sym, weight in top_weights[:5]
        ]
        upcoming = self.get_cgt_calendar(30)
        actionables = self.get_actionables()
        return DashboardSummary(
            total_value=total_value,
            cash=None,
            day_pl=None,
            top_weights=top_rows,
            upcoming_cgt=upcoming[:5],
            actionable_count=len(actionables),
        )


if TEXTUAL_AVAILABLE:

    class TextPrompt(ModalScreen[str | None]):
        def __init__(self, title: str, prompt: str, default: str = "") -> None:
            super().__init__()
            self.title_text = title
            self.prompt_text = prompt
            self.default = default
            self.result: str | None = None

        def compose(self) -> ComposeResult:
            yield Label(self.title_text, id="prompt-title")
            yield Label(self.prompt_text, id="prompt-message")
            yield Input(value=self.default, id="prompt-input")
            yield Button("OK", id="ok")
            yield Button("Cancel", id="cancel")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cancel":
                self.result = None
                self.dismiss(None)
            elif event.button.id == "ok":
                value = self.query_one("#prompt-input", Input).value.strip()
                self.result = value or None
                self.dismiss(self.result)


    class SnoozePrompt(TextPrompt):
        def __init__(self, default_days: int = 7) -> None:
            super().__init__(
                "Snooze Actionable",
                "Snooze for how many days?",
                str(default_days),
            )


    class PortfolioApp(App):
        CSS_PATH = Path(__file__).with_name("theme.tcss")
        BINDINGS = [
            ("1", "nav_dashboard", "Dashboard"),
            ("2", "nav_positions", "Positions"),
            ("3", "nav_lots", "Lots"),
            ("4", "nav_cgt", "CGT Calendar"),
            ("5", "nav_actionables", "Actionables"),
            ("t", "add_trade", "Add Trade"),
            ("r", "refresh_prices", "Refresh Prices"),
            ("q", "quit", "Quit"),
            ("?", "show_help", "Help"),
        ]

        def __init__(self, services: PortfolioServices, *, demo: bool = False):
            super().__init__()
            self.services = services
            self.demo = demo
            self.current_symbol: Optional[str] = None
            self.current_lot: Optional[int] = None
            self.header: HeaderWidget | None = None
            self.sidebar: Sidebar | None = None
            self.dashboard_view = DashboardView()
            self.positions_view = PositionsView()
            self.lots_view = LotsView()
            self.cgt_view = CGTCalendarView()
            self.actionables_view = ActionablesView()
            self.symbol_detail = SymbolDetailWidget()
            self.lot_detail = LotDetailWidget()
            self.toasts = ToastManager()

        def compose(self) -> ComposeResult:
            self.header = HeaderWidget(self.services.cfg)
            self.sidebar = Sidebar()
            content = Container(
                self.dashboard_view,
                self.positions_view,
                self.lots_view,
                self.cgt_view,
                self.actionables_view,
                id="main-content",
            )
            context_panel = Container(
                self.symbol_detail,
                self.lot_detail,
                id="context-panel",
            )
            yield self.header
            yield Horizontal(self.sidebar, content, context_panel)
            yield self.toasts
            yield Footer()

        def on_mount(self) -> None:
            self.sidebar.focus()
            self.show_dashboard()
            self.refresh_all()

        def on_key(self, event: events.Key) -> None:
            if event.key == "f":
                if self.focused is self.positions_view:
                    self.prompt_symbol_filter(self.positions_view.set_symbol_filter)
                    event.stop()
                elif self.focused is self.lots_view:
                    self.prompt_symbol_filter(self.lots_view.set_symbol_filter)
                    event.stop()
            elif event.key == "e" and self.focused is self.positions_view:
                symbol = self.current_symbol
                if not symbol:
                    return
                prompt = TextPrompt(
                    "Target Weight",
                    f"Set target weight for {symbol} (%)",
                    str(self.services.cfg.target_weights.get(symbol, 0) * 100)
                    if symbol in self.services.cfg.target_weights
                    else "",
                )
                self.push_screen(
                    prompt,
                    callback=lambda result: self._handle_weight_prompt(symbol, result),
                )
                event.stop()

        def prompt_symbol_filter(self, callback: Callable[[str | None], None]) -> None:
            prompt = TextPrompt("Filter", "Enter symbol (blank to clear)")

            def _finish(result: str | None) -> None:
                callback(result.upper() if result else None)

            self.push_screen(prompt, callback=_finish)

        def _handle_weight_prompt(self, symbol: str, result: str | None) -> None:
            if result is None:
                return
            try:
                weight = float(result) / 100
            except ValueError:
                self.toasts.error("Invalid weight")
                return
            self.services.cfg.target_weights[symbol] = weight
            self.toasts.success(f"Updated target weight for {symbol}")

        def refresh_all(self) -> None:
            summary = self.services.dashboard_summary()
            self.dashboard_view.update_summary(summary)
            positions = self.services.get_positions()
            self.positions_view.update_rows(positions)
            lots = self.services.get_lots()
            self.lots_view.update_rows(lots)
            cgt = self.services.get_cgt_calendar(
                self.services.cfg.rule_thresholds.cgt_window_days
            )
            self.cgt_view.update_rows(cgt)
            actionables = self.services.get_actionables()
            self.actionables_view.update_rows(actionables)
            status = self.services.get_price_status()
            if self.header:
                self.header.update_status(status)

        def action_nav_dashboard(self) -> None:
            self.show_dashboard()

        def show_dashboard(self) -> None:
            self.set_view(self.dashboard_view)
            if self.sidebar:
                self.sidebar.highlight("dashboard")

        def action_nav_positions(self) -> None:
            self.set_view(self.positions_view)
            if self.sidebar:
                self.sidebar.highlight("positions")

        def action_nav_lots(self) -> None:
            self.set_view(self.lots_view)
            if self.sidebar:
                self.sidebar.highlight("lots")

        def action_nav_cgt(self) -> None:
            self.set_view(self.cgt_view)
            if self.sidebar:
                self.sidebar.highlight("cgt")

        def action_nav_actionables(self) -> None:
            self.set_view(self.actionables_view)
            if self.sidebar:
                self.sidebar.highlight("actionables")

        def set_view(self, view: Widget) -> None:
            for widget in (
                self.dashboard_view,
                self.positions_view,
                self.lots_view,
                self.cgt_view,
                self.actionables_view,
            ):
                widget.display = widget is view

        def action_add_trade(self) -> None:
            modal = AddTradeModal(self.services.cfg)
            modal.on_submit = self._handle_trade_submit
            self.push_screen(modal)

        def _handle_trade_submit(self, data: dict) -> None:
            try:
                trade_input = TradeInput(
                    side=data["side"],
                    symbol=data["symbol"],
                    dt=data["datetime"],
                    qty=Decimal(data["qty"]),
                    price=Decimal(data["price"]),
                    fees=Decimal(data["fees"]),
                    exchange=data.get("exchange"),
                    note=data.get("note"),
                )
                self.services.record_trade(trade_input)
            except Exception as exc:  # noqa: BLE001
                self.toasts.error(str(exc))
            else:
                self.toasts.success("Trade recorded")
                self.refresh_all()

        def action_refresh_prices(self) -> None:
            symbols = [row.symbol for row in self.services.get_positions()]
            if not symbols:
                self.toasts.warning("No positions to refresh")
                return
            try:
                self.services.refresh_prices(symbols)
                status = self.services.get_price_status()
                if self.header:
                    self.header.update_status(status)
                self.refresh_all()
                self.toasts.success("Prices refreshed")
            except Exception as exc:  # noqa: BLE001
                self.toasts.error(f"Price refresh failed: {exc}")

        def action_show_help(self) -> None:
            help_text = Table(title="Shortcuts")
            help_text.add_column("Key")
            help_text.add_column("Action")
            for binding in self.BINDINGS:
                help_text.add_row(binding[0].upper(), binding[2])
            self.toasts.info(help_text)

        def on_position_selected(self, message: PositionSelected) -> None:
            self.current_symbol = message.symbol
            detail = self.services.get_symbol_detail(message.symbol)
            self.symbol_detail.update_detail(detail)
            self.symbol_detail.display = True
            self.lot_detail.display = False

        def on_lot_selected(self, message: LotSelected) -> None:
            self.show_lot_detail(message.lot_id)

        def show_lot_detail(self, lot_id: int) -> None:
            self.current_lot = lot_id
            detail = self.services.get_lot_detail(lot_id)
            self.lot_detail.update_detail(detail)
            self.lot_detail.display = True
            self.symbol_detail.display = False

        def action_quit(self) -> None:
            self.exit()

        def on_actionable_action(self, message: ActionableAction) -> None:
            if message.action == "done":
                self.services.mark_actionable_done(message.actionable_id)
                self.toasts.success("Actionable completed")
                self.refresh_all()
            elif message.action == "snooze":
                prompt = SnoozePrompt()
                self.push_screen(
                    prompt,
                    callback=lambda result: self._handle_snooze(
                        message.actionable_id, result
                    ),
                )

        def _handle_snooze(self, actionable_id: int, result: str | None) -> None:
            if not result:
                return
            try:
                days = int(result)
            except ValueError:
                self.toasts.error("Invalid snooze period")
                return
            self.services.snooze_actionable(actionable_id, days)
            self.toasts.success(f"Snoozed for {days} days")
            self.refresh_all()


    def run(argv: Optional[list[str]] = None) -> None:
        parser = argparse.ArgumentParser(description="Portfolio Textual UI")
        parser.add_argument("--config", type=Path, help="Path to config.toml", default=None)
        parser.add_argument("--demo", action="store_true", help="Run in demo mode")
        args = parser.parse_args(argv)
        cfg = load_config(args.config)
        services = build_services(cfg, demo=args.demo)
        app = PortfolioApp(services, demo=args.demo)
        app.run()


else:

    def run(argv: Optional[list[str]] = None) -> None:  # pragma: no cover - defensive
        raise ModuleNotFoundError(
            "The textual UI requires optional dependencies 'rich' and 'textual'. "
            "Install the project with the 'ui' extras to enable this feature."
        ) from _TEXTUAL_IMPORT_ERROR


def _provider_for(cfg: Config):
    return FallbackPriceProvider(cfg)


def build_services(cfg: Config, *, demo: bool = False) -> PortfolioServices:
    if demo:
        cfg = Config(**{**cfg.__dict__})
        cfg.db_path = Path(":memory:")
    ensure_app_dirs(cfg)
    database = Database(cfg)
    database.create_all()
    pricing = PriceService(cfg, _provider_for(cfg))
    services = PortfolioServices(cfg, database, pricing)
    if demo:
        seed_demo_data(services)
    return services


def seed_demo_data(services: PortfolioServices) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    symbols = ["AAA", "BBB", "CCC"]
    prices = {sym: Decimal("10") + Decimal(index) for index, sym in enumerate(symbols, start=1)}
    with services.db.session_scope() as session:
        for idx, symbol in enumerate(symbols, start=1):
            trade = repo.create_trade(
                session,
                {
                    "side": "BUY",
                    "symbol": symbol,
                    "dt": now - dt.timedelta(days=idx * 30),
                    "qty": Decimal("100"),
                    "price": prices[symbol],
                    "fees": Decimal("9.95"),
                    "exchange": "ASX",
                    "note": "Seed",
                },
            )
            repo.create_lot(
                session,
                symbol=symbol,
                acquired_at=trade.dt,
                qty=trade.qty,
                cost_base=trade.qty * trade.price,
                threshold_date=(trade.dt + dt.timedelta(days=365)).date(),
                trade_id=trade.id,
            )
        session.flush()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
