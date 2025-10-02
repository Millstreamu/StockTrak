"""Textual application entrypoint for the portfolio tool."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised indirectly in tests
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.screen import ModalScreen
    from textual.widgets import Footer, Header, Static, TabbedContent, TabPane
except ModuleNotFoundError:  # pragma: no cover - used when textual is optional
    from ._textual_stub import (  # type: ignore[assignment]
        App,
        ComposeResult,
        Container,
        Footer,
        Header,
        ModalScreen,
        Static,
        TabbedContent,
        TabPane,
    )

from ...core.config import DEFAULT_CONFIG_PATH, ensure_config, load_config
from ...core.pricing import PricingService
from ...core.reports import ReportingService
from ...core.rules import ActionableService
from ...core.services import PortfolioService
from ...data import JSONRepository, SQLiteRepository
from ...plugins.pricing import get_provider
from .views import (
    ActionablesView,
    CGTCalendarView,
    ConfigView,
    DashboardView,
    LotsView,
    PositionsView,
    PricesView,
    TradesView,
)


@dataclass
class AppServices:
    repo: Any
    portfolio: PortfolioService
    reporting: ReportingService
    pricing: PricingService
    actionables: ActionableService
    config: dict
    config_path: Path


class HelpModal(ModalScreen[None]):
    """Simple overlay listing key bindings."""

    def compose(self) -> ComposeResult:
        text = (
            "[b]Portfolio Tool — Key Bindings[/b]\n"
            "F1 Help  |  Q Quit  |  R Refresh  |  / Search\n"
            "A Add  |  E Edit  |  D Delete  |  S Save/Export"
        )
        yield Container(Static(text, id="help-text"), id="help-container")


class PortfolioApp(App[None]):
    CSS = ""
    BINDINGS = [
        ("f1", "help", "Help"),
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("/", "focus_search", "Search"),
        ("a", "add", "Add"),
        ("e", "edit", "Edit"),
        ("d", "delete", "Delete"),
        ("s", "save", "Save/Export"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Previous"),
    ]

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._config_path = Path(config_path or DEFAULT_CONFIG_PATH)
        self._data_dir = Path(data_dir or "data")
        self.services: AppServices | None = None
        self._view_map: dict[str, Any] = {}
        self._active_view = None

        self.dashboard_view = DashboardView()
        self.trades_view = TradesView()
        self.positions_view = PositionsView()
        self.lots_view = LotsView()
        self.cgt_view = CGTCalendarView()
        self.actionables_view = ActionablesView()
        self.prices_view = PricesView()
        self.config_view = ConfigView()

    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            with TabPane("Dashboard", id="tab-dashboard"):
                yield self.dashboard_view
            with TabPane("Trades", id="tab-trades"):
                yield self.trades_view
            with TabPane("Positions", id="tab-positions"):
                yield self.positions_view
            with TabPane("Lots", id="tab-lots"):
                yield self.lots_view
            with TabPane("CGT", id="tab-cgt"):
                yield self.cgt_view
            with TabPane("Actionables", id="tab-actionables"):
                yield self.actionables_view
            with TabPane("Prices", id="tab-prices"):
                yield self.prices_view
            with TabPane("Config", id="tab-config"):
                yield self.config_view
        yield Footer()

    # ------------------------------------------------------------------
    def on_mount(self) -> None:
        self.services = self._build_services()
        self._view_map = {
            "tab-dashboard": self.dashboard_view,
            "tab-trades": self.trades_view,
            "tab-positions": self.positions_view,
            "tab-lots": self.lots_view,
            "tab-cgt": self.cgt_view,
            "tab-actionables": self.actionables_view,
            "tab-prices": self.prices_view,
            "tab-config": self.config_view,
        }
        self._active_view = self.dashboard_view
        for view in self._view_map.values():
            view.refresh_view()

    # ------------------------------------------------------------------
    def on_unmount(self) -> None:
        if self.services:
            self.services.repo.close()

    # ------------------------------------------------------------------
    def _build_services(self) -> AppServices:
        config_file = ensure_config(self._config_path)
        config = load_config(config_file)
        repo = self._open_repository(config)
        portfolio = PortfolioService(
            repo,
            timezone=config.get("timezone", "Australia/Brisbane"),
            lot_matching=config.get("lot_matching", "FIFO"),
            brokerage_allocation=config.get("brokerage_allocation", "BUY"),
        )
        reporting = ReportingService(
            repo,
            timezone=config.get("timezone", "Australia/Brisbane"),
            base_currency=config.get("base_currency", "AUD"),
            portfolio_service=portfolio,
        )
        pricing = PricingService(
            repo,
            get_provider(config.get("prices", {}).get("provider", "manual_inline")),
            cache_ttl_minutes=config.get("prices", {}).get("cache_ttl_minutes", 15),
            stale_price_max_minutes=config.get("prices", {}).get("stale_price_max_minutes", 60),
            timezone=config.get("timezone", "Australia/Brisbane"),
            exchange_suffix_map=config.get("prices", {}).get("exchange_suffix_map", {}),
        )
        actionables = ActionableService(
            repo,
            portfolio_service=portfolio,
            reporting_service=reporting,
            pricing_service=pricing,
            timezone=config.get("timezone", "Australia/Brisbane"),
            target_weights=config.get("target_weights", {}),
            rule_thresholds=config.get("rule_thresholds", {}),
        )
        return AppServices(
            repo=repo,
            portfolio=portfolio,
            reporting=reporting,
            pricing=pricing,
            actionables=actionables,
            config=config,
            config_path=config_file,
        )

    # ------------------------------------------------------------------
    def _open_repository(self, config: dict) -> Any:
        storage_cfg = config.get("storage", {})
        backend = (storage_cfg.get("backend") or "sqlite").lower()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if backend == "sqlite":
            path = storage_cfg.get("path") or self._data_dir / "portfolio.sqlite"
            return SQLiteRepository(Path(path))
        if backend == "json":
            path = storage_cfg.get("path") or self._data_dir / "portfolio.json"
            return JSONRepository(Path(path))
        raise RuntimeError(f"Unsupported storage backend: {backend}")

    # ------------------------------------------------------------------
    def _current_view(self):
        return self._active_view

    # ------------------------------------------------------------------
    async def _invoke_view(self, name: str) -> None:
        view = self._current_view()
        if not view:
            return
        handler = getattr(view, name, None)
        if not handler:
            return
        result = handler()
        if inspect.isawaitable(result):
            await result

    # ------------------------------------------------------------------
    async def action_add(self) -> None:
        await self._invoke_view("handle_add")

    async def action_edit(self) -> None:
        await self._invoke_view("handle_edit")

    async def action_delete(self) -> None:
        await self._invoke_view("handle_delete")

    async def action_save(self) -> None:
        await self._invoke_view("handle_save")

    async def action_refresh(self) -> None:
        await self._invoke_view("handle_refresh")
        view = self._current_view()
        if view:
            view.refresh_view()

    def action_focus_search(self) -> None:
        view = self._current_view()
        if view:
            view.focus_search()

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_quit(self) -> None:
        self.exit()

    # ------------------------------------------------------------------
    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        view = self._view_map.get(event.tab.id)
        if view:
            self._active_view = view
            view.refresh_view()


def run() -> None:
    PortfolioApp().run()


if __name__ == "__main__":
    run()
