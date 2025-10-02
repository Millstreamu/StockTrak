"""Actionables management view."""
from __future__ import annotations

from typing import Any

from ..widgets.forms import SnoozeForm
from ..widgets.toasts import show_toast
from .base import TableView


class ActionablesView(TableView):
    def __init__(self) -> None:
        super().__init__(
            title="Actionables",
            columns=[
                ("id", "ID"),
                ("type", "Type"),
                ("symbol", "Symbol"),
                ("message", "Message"),
                ("status", "Status"),
                ("snoozed_until", "Snoozed Until"),
                ("updated_at", "Updated"),
            ],
            key_field="id",
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
        items = services.actionables.evaluate_rules(include_snoozed=True)
        self._rows = [
            {
                "id": item.id,
                "type": item.type,
                "symbol": item.symbol,
                "message": item.message,
                "status": item.status,
                "snoozed_until": item.snoozed_until.isoformat() if item.snoozed_until else "",
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]

    def _load_page(self, page: int, size: int, query: str):
        self._compute_rows()
        data = self._rows
        if query:
            q = query.upper()
            data = [row for row in data if q in str(row.get("symbol", "")).upper() or q in str(row.get("message", "")).upper()]
        total = len(data)
        start = page * size
        end = start + size
        return data[start:end], total

    async def handle_add(self) -> None:
        self.refresh_view()
        show_toast(self.app, "Rules evaluated", severity="information")

    async def handle_edit(self) -> None:
        services = self.services
        if services is None:
            return
        selected = self.table.get_selected_row()
        if not selected:
            show_toast(self.app, "Select an actionable to snooze", severity="warning")
            return
        form = SnoozeForm()
        days = await self.app.push_screen_wait(form)
        if not days:
            return
        actionable_id = int(selected["id"])
        services.actionables.snooze(actionable_id, int(days))
        self.refresh_view()
        show_toast(self.app, f"Snoozed actionable {actionable_id}", severity="success")

    def handle_delete(self) -> None:
        services = self.services
        if services is None:
            return
        selected = self.table.get_selected_row()
        if not selected:
            show_toast(self.app, "Select an actionable to complete", severity="warning")
            return
        actionable_id = int(selected["id"])
        services.actionables.complete(actionable_id)
        self.refresh_view()
        show_toast(self.app, f"Completed actionable {actionable_id}", severity="success")


__all__ = ["ActionablesView"]
