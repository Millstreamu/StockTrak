from __future__ import annotations

import argparse
import datetime as dt
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Optional

from sqlalchemy import create_engine, select

from portfolio_tool.config import Config, load_config
from portfolio_tool.core.diagnostics import (
    PortfolioDiagnostics,
    PriceReason,
    collect_diagnostics,
    determine_price_status,
)
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
from portfolio_tool.data.init_db import ensure_db
from portfolio_tool.data.repo import Database
from portfolio_tool.providers.fallback_provider import FallbackPriceProvider
from portfolio_tool.logging_utils import configure_logging, get_api_log_path

from .events import DataChanged

try:  # pragma: no cover - exercised indirectly via textual UI usage
    from rich.table import Table
    from textual import events, on
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widget import Widget
    from textual.widgets import Button, Footer, Input, Label, Static
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

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
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
    reason: PriceReason


@dataclass
class DashboardSummary:
    total_value: Decimal
    cash: Decimal | None
    day_pl: Decimal | None
    top_weights: list[dict]
    upcoming_cgt: list[LotRow]
    actionable_count: int


log = logging.getLogger("ui")

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

    def get_all_lots(self) -> list[LotRow]:
        return self.get_lots()

    def get_cgt_calendar(self, days: int | None = None) -> list[LotRow]:
        window = days or self.cfg.rule_thresholds.cgt_window_days
        with self._session() as session:
            return build_cgt_calendar(session, self.cfg, window)

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

    def get_diagnostics(self) -> PortfolioDiagnostics:
        with self._session() as session:
            return collect_diagnostics(self.cfg, session)

    def get_price_status(self) -> PriceStatus:
        with self._session() as session:
            diagnostics = collect_diagnostics(self.cfg, session)
        asof, reason = determine_price_status(diagnostics)
        return PriceStatus(asof=asof, stale=reason != "ok", reason=reason)

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


    class DiagnosticsModal(ModalScreen[None]):
        def __init__(
            self,
            diagnostics: PortfolioDiagnostics,
            bindings: list[tuple[str, str, str]],
        ) -> None:
            super().__init__()
            self.diagnostics = diagnostics
            self.bindings = bindings

        def compose(self) -> ComposeResult:
            diag_table = Table(title="Portfolio Diagnostics")
            diag_table.add_column("Metric")
            diag_table.add_column("Value", overflow="fold")
            diag_table.add_row("DB Path", str(self.diagnostics.db_path))
            diag_table.add_row("DB Exists", "Yes" if self.diagnostics.db_exists else "No")
            diag_table.add_row("Trades", str(self.diagnostics.trade_count))
            diag_table.add_row("Lots", str(self.diagnostics.lot_count))
            diag_table.add_row("Prices", str(self.diagnostics.price_count))
            diag_table.add_row("Actionables", str(self.diagnostics.actionable_count))
            latest = self.diagnostics.latest_price
            if latest:
                asof = latest.asof.astimezone(dt.timezone.utc).isoformat() if latest.asof else "—"
                diag_table.add_row("Latest Price", f"{latest.symbol} @ {asof}")
                diag_table.add_row("Stale", "Yes" if latest.is_stale else "No")
            else:
                diag_table.add_row("Latest Price", "—")
                diag_table.add_row("Stale", "—")
            diag_table.add_row("Offline Mode", "Yes" if self.diagnostics.offline_mode else "No")
            diag_table.add_row("Price Provider", self.diagnostics.price_provider)
            diag_table.add_row(
                "Price TTL", f"{self.diagnostics.price_ttl_minutes} minutes"
            )
            api_log = self.diagnostics.api_log_path
            diag_table.add_row("API Log", str(api_log) if api_log else "—")

            shortcuts_table = Table(title="Shortcuts")
            shortcuts_table.add_column("Key")
            shortcuts_table.add_column("Action")
            for key, _action, description in self.bindings:
                shortcuts_table.add_row(key.upper(), description)

            yield Static(diag_table, id="diagnostics-table")
            yield Static(shortcuts_table, id="shortcuts-table")
            yield Button("Close", id="close")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "close":
                self.dismiss(None)


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
            configure_logging()
            super().__init__()
            self.services = services
            self.demo = demo
            self.current_symbol: Optional[str] = None
            self.current_lot: Optional[int] = None
            self.header: HeaderWidget | None = None
            self.sidebar: Sidebar | None = None
            self.main_container: Container | None = None
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
            self.main_container = content
            context_panel = Container(
                self.symbol_detail,
                self.lot_detail,
                id="context-panel",
            )
            yield self.header
            yield Horizontal(self.sidebar, content, context_panel)
            yield self.toasts
            yield Footer()

        def toast(self, message: str, level: str = "info") -> None:
            if not self.toasts:
                return
            handler = getattr(self.toasts, level, None)
            if callable(handler):
                handler(message)
            else:
                self.toasts.info(message)

        def on_mount(self) -> None:
            if self.sidebar:
                self.sidebar.highlight("dashboard")
                try:
                    self.sidebar.query_one("#nav-dashboard", Button).focus()
                except Exception:  # pragma: no cover - focus fallback
                    self.sidebar.focus()
            self.show_dashboard()
            self.refresh_all()
            api_log_path = get_api_log_path()
            if api_log_path:
                self.toast(f"API log: {api_log_path}")

        def on_key(self, event: events.Key) -> None:
            key = event.key
            if key == "1":
                self.show_dashboard()
                self.toast("Dashboard")
                event.stop()
                return
            if key == "2":
                self.show_positions()
                self.toast("Positions")
                event.stop()
                return
            if key == "3":
                self.show_lots()
                self.toast("Lots")
                event.stop()
                return
            if key == "4":
                self.show_cgt()
                self.toast("CGT Calendar")
                event.stop()
                return
            if key == "5":
                self.show_actionables()
                self.toast("Actionables")
                event.stop()
                return

            if key == "f":
                if self.focused is self.positions_view:
                    self.prompt_symbol_filter(self.positions_view.set_symbol_filter)
                    event.stop()
                elif self.focused is self.lots_view:
                    self.prompt_symbol_filter(self.lots_view.set_symbol_filter)
                    event.stop()
            elif key == "e" and self.focused is self.positions_view:
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

        def _ensure_mounted(self, view: Widget) -> None:
            if not view.parent and self.main_container:
                self.main_container.mount(view)

        def _handle_weight_prompt(self, symbol: str, result: str | None) -> None:
            if result is None:
                return
            try:
                weight = float(result) / 100
            except ValueError:
                self.toast("Invalid weight", level="error")
                return
            self.services.cfg.target_weights[symbol] = weight
            self.toast(f"Updated target weight for {symbol}", level="success")

        def refresh_all(self) -> None:
            try:
                summary = self.services.dashboard_summary()
                self.dashboard_view.update_summary(summary)
                log.debug("Dashboard summary refreshed")
            except Exception:  # noqa: BLE001
                log.exception("Dashboard refresh failed")
                self.toast("Dashboard refresh failed — see logs", level="warning")

            try:
                positions = self.services.get_positions()
                self.positions_view.update_rows(positions)
                log.debug("Positions: %d rows", len(positions))
            except Exception:  # noqa: BLE001
                log.exception("Positions refresh failed")
                self.toast("Positions refresh failed — see logs", level="warning")

            try:
                lots = self.services.get_all_lots()
                self.lots_view.update_rows(lots)
                log.debug("Lots: %d rows", len(lots))
            except Exception:  # noqa: BLE001
                log.exception("Lots refresh failed")
                self.toast("Lots refresh failed — see logs", level="warning")

            try:
                window = self.services.cfg.rule_thresholds.cgt_window_days
                cgt = self.services.get_cgt_calendar(window)
                self.cgt_view.update_rows(cgt)
                log.debug("CGT items: %d", len(cgt))
            except Exception:  # noqa: BLE001
                log.exception("CGT refresh failed")
                self.toast("CGT refresh failed — see logs", level="warning")

            try:
                actionables = self.services.get_actionables()
                self.actionables_view.update_rows(actionables)
                log.debug("Actionables: %d", len(actionables))
            except Exception:  # noqa: BLE001
                log.exception("Actionables refresh failed")
                self.toast("Actionables refresh failed — see logs", level="warning")

            try:
                status = self.services.get_price_status()
                if self.header:
                    self.header.update_status(status)
            except Exception:  # noqa: BLE001
                log.exception("Header status refresh failed")

            if self.current_symbol and self.symbol_detail:
                try:
                    detail = self.services.get_symbol_detail(self.current_symbol)
                    self.symbol_detail.update_detail(detail)
                except Exception:  # noqa: BLE001
                    log.exception("Symbol detail refresh failed")

            if self.current_lot and self.lot_detail:
                try:
                    detail = self.services.get_lot_detail(self.current_lot)
                    self.lot_detail.update_detail(detail)
                except Exception:  # noqa: BLE001
                    log.exception("Lot detail refresh failed")

        @on(DataChanged)
        def _on_data_changed(self, _: DataChanged) -> None:
            self.refresh_all()

        def action_nav_dashboard(self) -> None:
            self.show_dashboard()
            self.toast("Dashboard")

        def show_dashboard(self) -> None:
            self._ensure_mounted(self.dashboard_view)
            self.set_view(self.dashboard_view)
            if self.main_container:
                self.main_container.visible = True
            try:
                summary = self.services.dashboard_summary()
                self.dashboard_view.update_summary(summary)
            except Exception:  # noqa: BLE001
                log.exception("Dashboard refresh failed")
                self.toast("Dashboard refresh failed — see logs", level="warning")
            if self.sidebar:
                self.sidebar.highlight("dashboard")

        def action_nav_positions(self) -> None:
            self.show_positions()
            self.toast("Positions")

        def action_nav_lots(self) -> None:
            self.show_lots()
            self.toast("Lots")

        def action_nav_cgt(self) -> None:
            self.show_cgt()
            self.toast("CGT Calendar")

        def action_nav_actionables(self) -> None:
            self.show_actionables()
            self.toast("Actionables")

        def show_positions(self) -> None:
            self._ensure_mounted(self.positions_view)
            self.set_view(self.positions_view)
            if self.main_container:
                self.main_container.visible = True
            try:
                rows = self.services.get_positions()
                self.positions_view.update_rows(rows)
            except Exception:  # noqa: BLE001
                log.exception("Positions refresh failed")
                self.toast("Positions refresh failed — see logs", level="warning")
            if self.sidebar:
                self.sidebar.highlight("positions")

        def show_lots(self) -> None:
            self._ensure_mounted(self.lots_view)
            self.set_view(self.lots_view)
            if self.main_container:
                self.main_container.visible = True
            try:
                rows = self.services.get_all_lots()
                self.lots_view.update_rows(rows)
            except Exception:  # noqa: BLE001
                log.exception("Lots refresh failed")
                self.toast("Lots refresh failed — see logs", level="warning")
            if self.sidebar:
                self.sidebar.highlight("lots")

        def show_cgt(self) -> None:
            self._ensure_mounted(self.cgt_view)
            self.set_view(self.cgt_view)
            if self.main_container:
                self.main_container.visible = True
            try:
                window = self.services.cfg.rule_thresholds.cgt_window_days
                rows = self.services.get_cgt_calendar(window)
                self.cgt_view.update_rows(rows)
            except Exception:  # noqa: BLE001
                log.exception("CGT refresh failed")
                self.toast("CGT refresh failed — see logs", level="warning")
            if self.sidebar:
                self.sidebar.highlight("cgt")

        def show_actionables(self) -> None:
            self._ensure_mounted(self.actionables_view)
            self.set_view(self.actionables_view)
            if self.main_container:
                self.main_container.visible = True
            try:
                rows = self.services.get_actionables()
                self.actionables_view.update_rows(rows)
            except Exception:  # noqa: BLE001
                log.exception("Actionables refresh failed")
                self.toast("Actionables refresh failed — see logs", level="warning")
            if self.sidebar:
                self.sidebar.highlight("actionables")

        def set_view(self, view: Widget) -> None:
            self._ensure_mounted(view)
            for widget in (
                self.dashboard_view,
                self.positions_view,
                self.lots_view,
                self.cgt_view,
                self.actionables_view,
            ):
                if widget.parent:
                    widget.display = widget is view

        @on(Button.Pressed, "#nav-dashboard")
        def _go_dashboard(self, _: Button.Pressed) -> None:
            self.show_dashboard()
            self.toast("Dashboard")

        @on(Button.Pressed, "#nav-positions")
        def _go_positions(self, _: Button.Pressed) -> None:
            self.show_positions()
            self.toast("Positions")

        @on(Button.Pressed, "#nav-lots")
        def _go_lots(self, _: Button.Pressed) -> None:
            self.show_lots()
            self.toast("Lots")

        @on(Button.Pressed, "#nav-cgt")
        def _go_cgt(self, _: Button.Pressed) -> None:
            self.show_cgt()
            self.toast("CGT Calendar")

        @on(Button.Pressed, "#nav-actionables")
        def _go_actionables(self, _: Button.Pressed) -> None:
            self.show_actionables()
            self.toast("Actionables")

        def action_add_trade(self) -> None:
            modal = AddTradeModal(self.services.cfg)
            modal.on_submit = self._handle_trade_submit
            self.push_screen(modal)

        def _handle_trade_submit(self, data: dict) -> bool:
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
                self.toast(str(exc), level="error")
                return False
            return True

        def action_refresh_prices(self) -> None:
            symbols = [row.symbol for row in self.services.get_positions()]
            if not symbols:
                self.toast("No positions to refresh", level="warning")
                return
            try:
                self.services.refresh_prices(symbols)
                status = self.services.get_price_status()
                if self.header:
                    self.header.update_status(status)
                self.refresh_all()
                self.toast("Prices refreshed", level="success")
            except Exception as exc:  # noqa: BLE001
                self.toast(f"Price refresh failed: {exc}", level="error")

        def action_show_help(self) -> None:
            try:
                diagnostics = self.services.get_diagnostics()
            except Exception as exc:  # noqa: BLE001
                self.toast(f"Diagnostics failed: {exc}", level="error")
                return
            self.push_screen(DiagnosticsModal(diagnostics, self.BINDINGS))

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
                self.toast("Actionable completed", level="success")
                self.post_message(DataChanged())
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
                self.toast("Invalid snooze period", level="error")
                return
            self.services.snooze_actionable(actionable_id, days)
            self.toast(f"Snoozed for {days} days", level="success")
            self.post_message(DataChanged())


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

    class PortfolioApp:  # pragma: no cover - textual optional
        """Placeholder PortfolioApp used when textual dependencies are unavailable."""

        def __init__(self, *_: object, **__: object) -> None:
            raise ModuleNotFoundError(
                "The textual UI requires optional dependencies 'rich' and 'textual'. "
                "Install the project with the 'ui' extras to enable this feature."
            ) from _TEXTUAL_IMPORT_ERROR

        def run(self) -> None:
            raise ModuleNotFoundError(
                "The textual UI requires optional dependencies 'rich' and 'textual'. "
                "Install the project with the 'ui' extras to enable this feature."
            ) from _TEXTUAL_IMPORT_ERROR

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
        engine = create_engine("sqlite+pysqlite:///:memory:")
        models.Base.metadata.create_all(engine)
        cfg.db_path = Path(":memory:")
    else:
        engine = ensure_db()
    database = Database(engine)
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
