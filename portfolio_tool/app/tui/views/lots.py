"""Lots ledger view."""
from __future__ import annotations

from typing import Any

from ..widgets.toasts import show_toast
from .base import TableView


class LotsView(TableView):
    def __init__(self) -> None:
        super().__init__(
            title="Lots",
            columns=[
                ("lot_id", "Lot"),
                ("symbol", "Symbol"),
                ("acquired_at", "Acquired"),
                ("threshold_date", "CGT Threshold"),
                ("original_qty", "Original Qty"),
                ("qty_remaining", "Qty Remaining"),
                ("cost_base_remaining", "Cost Base"),
                ("status", "Status"),
            ],
            key_field="lot_id",
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
        reporting = services.reporting
        self._rows = reporting.lots_ledger()

    def _load_page(self, page: int, size: int, query: str):
        self._compute_rows()
        data = self._rows
        if query:
            q = query.upper()
            data = [row for row in data if q in str(row.get("symbol", "")).upper()]
        total = len(data)
        start = page * size
        end = start + size
        return data[start:end], total

    def handle_add(self) -> None:
        show_toast(self.app, "Lots derive from trades. Add trades instead.", severity="information")


__all__ = ["LotsView"]
