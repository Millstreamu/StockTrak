from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from textual.widget import Widget

if TYPE_CHECKING:
    from ..textual_app import DashboardSummary


class DashboardView(Widget):
    """Render dashboard cards."""

    DEFAULT_CSS = "DashboardView { height: 100%; }"

    def __init__(self) -> None:
        super().__init__()
        self.summary: "DashboardSummary | None" = None

    def update_summary(self, summary: DashboardSummary) -> None:
        self.summary = summary
        self.refresh()

    def render(self) -> RenderableType:
        if not self.summary:
            return Panel("Loading…", title="Dashboard")
        grid = Table.grid(padding=(0, 1))
        grid.add_column()
        grid.add_column()
        grid.add_row(self._metrics_panel(), self._weights_panel())
        grid.add_row(self._cgt_panel(), self._actionables_panel())
        return grid

    def _metrics_panel(self) -> Panel:
        table = Table.grid(padding=1)
        table.add_row(f"Total Market Value: [bold]{self.summary.total_value:.2f}[/bold]")
        if self.summary.cash is not None:
            table.add_row(f"Cash: [bold]{self.summary.cash:.2f}[/bold]")
        if self.summary.day_pl is not None:
            table.add_row(f"Day P/L: [bold]{self.summary.day_pl:.2f}[/bold]")
        else:
            table.add_row("Day P/L: —")
        return Panel(table, title="Portfolio")

    def _weights_panel(self) -> Panel:
        table = Table(title="Top Weights", expand=True)
        table.add_column("Symbol")
        table.add_column("Weight")
        for row in self.summary.top_weights:
            weight = row["weight"] * 100
            table.add_row(row["symbol"], f"{weight:.2f}%")
        if not self.summary.top_weights:
            table.add_row("—", "—")
        return Panel(table)

    def _cgt_panel(self) -> Panel:
        table = Table(title="Upcoming CGT", expand=True)
        table.add_column("Symbol")
        table.add_column("Threshold")
        table.add_column("Qty")
        for lot in self.summary.upcoming_cgt:
            table.add_row(
                lot.symbol,
                lot.threshold_date.isoformat(),
                f"{lot.qty_remaining:.2f}",
            )
        if not self.summary.upcoming_cgt:
            table.add_row("—", "—", "—")
        return Panel(table)

    def _actionables_panel(self) -> Panel:
        table = Table.grid(padding=1)
        table.add_row(f"Open Actionables: [bold]{self.summary.actionable_count}[/bold]")
        return Panel(table, title="Actionables")
