"""Dashboard view showing high level portfolio metrics."""
from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import Static
from zoneinfo import ZoneInfo

from .base import PortfolioView


class DashboardView(PortfolioView):
    """Display a quick snapshot of the portfolio."""

    def __init__(self) -> None:
        super().__init__(id="view-dashboard")
        self._summary = Static("", classes="dashboard-summary")

    def compose(self) -> ComposeResult:
        yield Static("Dashboard", classes="view-title")
        yield self._summary

    def refresh_view(self) -> None:
        services = self.services
        if services is None:
            return
        tz_name = services.config.get("timezone", "Australia/Brisbane")
        tz = ZoneInfo(tz_name)
        pricing = services.pricing
        repo = services.repo
        reporting = services.reporting
        actionables = services.actionables

        symbols = sorted({row["symbol"] for row in repo.list_lots(only_open=True)})
        quotes = pricing.get_cached(symbols)
        snapshot = reporting.positions_snapshot(datetime.now(tz=tz), quotes)
        total_mv = 0.0
        total_cost = 0.0
        holdings = 0
        for row in snapshot:
            if row.get("symbol") == "TOTAL":
                total_mv = float(row.get("market_value") or 0.0)
                total_cost = float(row.get("cost_base") or 0.0)
            else:
                holdings += 1
        unrealised = total_mv - total_cost
        actionables_list = actionables.list_actionables()
        open_items = sum(1 for item in actionables_list if item.status != "DONE")
        summary = (
            f"Holdings: [bold]{holdings}[/bold]\n"
            f"Market Value: [bold]{total_mv:,.2f} {services.config.get('base_currency', 'AUD')}[/bold]\n"
            f"Unrealised P/L: [bold]{unrealised:,.2f}[/bold]\n"
            f"Actionables: [bold]{open_items} open[/bold]"
        )
        self._summary.update(summary)


__all__ = ["DashboardView"]
