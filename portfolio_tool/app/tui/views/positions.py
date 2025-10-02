"""Positions view showing current holdings."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from zoneinfo import ZoneInfo

from ..widgets.toasts import show_toast
from .base import TableView


class PositionsView(TableView):
    def __init__(self) -> None:
        super().__init__(
            title="Positions",
            columns=[
                ("symbol", "Symbol"),
                ("quantity", "Qty"),
                ("avg_cost", "Avg Cost"),
                ("cost_base", "Cost Base"),
                ("price", "Price"),
                ("market_value", "Market Value"),
                ("weight_pct", "Weight %"),
            ],
            key_field="symbol",
        )
        self._rows: list[dict[str, Any]] = []

    def on_mount(self) -> None:
        self.set_loader(self._load_page)
        super().on_mount()

    def _compute_rows(self) -> None:
        services = self.services
        if services is None:
            self._rows = []
            return
        tz = ZoneInfo(services.config.get("timezone", "Australia/Brisbane"))
        repo = services.repo
        reporting = services.reporting
        pricing = services.pricing
        symbols = sorted({row["symbol"] for row in repo.list_lots(only_open=True)})
        quotes = pricing.get_cached(symbols)
        snapshot = reporting.positions_snapshot(datetime.now(tz=tz), quotes)
        self._rows = snapshot

    def _load_page(self, page: int, size: int, query: str):
        self._compute_rows()
        data = self._rows
        if query:
            q = query.upper()
            data = [row for row in data if q in str(row.get("symbol", "")).upper()]
        total = len(data)
        start = page * size
        end = start + size
        page_rows = data[start:end]
        return page_rows, total

    def handle_save(self) -> None:
        show_toast(self.app, "Use CLI exports for detailed reports", severity="information")


__all__ = ["PositionsView"]
