"""CGT calendar view."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from zoneinfo import ZoneInfo

from ..widgets.toasts import show_toast
from .base import TableView


class CGTCalendarView(TableView):
    def __init__(self) -> None:
        super().__init__(
            title="CGT Calendar",
            columns=[
                ("lot_id", "Lot"),
                ("symbol", "Symbol"),
                ("threshold_date", "Threshold"),
                ("days_until", "Days"),
                ("eligible_for_discount", "Eligible"),
                ("qty_remaining", "Qty"),
            ],
            key_field="lot_id",
        )
        self._rows: list[dict[str, Any]] = []
        self._window_days = 60

    def on_mount(self) -> None:
        self.set_loader(self._load_page)
        super().on_mount()

    def _compute_rows(self) -> None:
        services = self.services
        if services is None:
            self._rows = []
            return
        tz = ZoneInfo(services.config.get("timezone", "Australia/Brisbane"))
        reporting = services.reporting
        self._rows = reporting.cgt_calendar(
            asof=datetime.now(tz=tz),
            window_days=self._window_days,
        )

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
        options = [30, 60, 90]
        idx = options.index(self._window_days)
        self._window_days = options[(idx + 1) % len(options)]
        self.refresh_view()
        show_toast(self.app, f"CGT window set to {self._window_days} days", severity="information")

    def status_text(self) -> str:
        return f"Window {self._window_days} days | {self.table.page_info()}"



__all__ = ["CGTCalendarView"]
