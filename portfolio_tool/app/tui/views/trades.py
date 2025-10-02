"""Trades view providing add/edit/delete operations."""
from __future__ import annotations

from typing import Any

from portfolio_tool.core.models import Transaction
from ..widgets.forms import TradeForm
from ..widgets.toasts import show_toast
from .base import TableView


class TradesView(TableView):
    """List transactions with editing capabilities."""

    def __init__(self) -> None:
        super().__init__(
            title="Trades",
            columns=[
                ("id", "ID"),
                ("dt", "When"),
                ("type", "Type"),
                ("symbol", "Symbol"),
                ("qty", "Qty"),
                ("price", "Price"),
                ("fees", "Fees"),
                ("broker_ref", "Broker Ref"),
            ],
            key_field="id",
        )
        self._cache: list[dict[str, Any]] = []
        self._dirty = True

    def on_mount(self) -> None:
        services = self.services
        if services is None:
            return
        self.set_loader(self._load_page)
        super().on_mount()

    def _ensure_cache(self) -> None:
        if not self._dirty:
            return
        services = self.services
        if services is None:
            return
        repo = services.repo
        rows = repo.list_transactions(order="desc")
        self._cache = rows
        self._dirty = False

    def _load_page(self, page: int, size: int, query: str):
        self._ensure_cache()
        data = self._cache
        if query:
            q = query.upper()
            data = [
                row
                for row in data
                if q in str(row.get("symbol", "")).upper()
                or q in str(row.get("type", "")).upper()
                or q in str(row.get("notes", "")).upper()
            ]
        total = len(data)
        start = page * size
        end = start + size
        page_rows = data[start:end]
        display_rows: list[dict[str, Any]] = []
        for row in page_rows:
            display_rows.append(
                {
                    "id": row["id"],
                    "dt": row["dt"],
                    "type": row["type"],
                    "symbol": row["symbol"],
                    "qty": float(row["qty"]),
                    "price": float(row["price"]),
                    "fees": float(row.get("fees", 0.0)),
                    "broker_ref": row.get("broker_ref"),
                    "_raw": row,
                }
            )
        return display_rows, total

    async def handle_add(self) -> None:
        services = self.services
        if services is None:
            return
        form = TradeForm(
            title="Add Trade",
            timezone=services.config.get("timezone", "Australia/Brisbane"),
        )
        result = await self.app.push_screen_wait(form)
        if not result:
            return
        txn = Transaction(
            dt=result["dt"],
            type=result["type"],
            symbol=result["symbol"],
            qty=float(result["qty"]),
            price=float(result["price"]),
            fees=float(result["fees"]),
            broker_ref=result.get("broker_ref"),
            notes=result.get("notes"),
            exchange=result.get("exchange"),
        )
        services.portfolio.record_trade(txn)
        self._dirty = True
        services.actionables.evaluate_rules(include_snoozed=True)
        self.refresh_view()
        show_toast(self.app, "Trade recorded", severity="success")

    async def handle_edit(self) -> None:
        services = self.services
        if services is None:
            return
        selected = self.table.get_selected_row()
        if not selected:
            show_toast(self.app, "Select a trade to edit", severity="warning")
            return
        raw = selected.get("_raw") or {}
        initial = {
            "type": raw.get("type"),
            "symbol": raw.get("symbol"),
            "qty": raw.get("qty"),
            "price": raw.get("price"),
            "fees": raw.get("fees"),
            "dt": raw.get("dt"),
            "broker_ref": raw.get("broker_ref"),
            "notes": raw.get("notes"),
            "exchange": raw.get("exchange"),
        }
        form = TradeForm(
            title=f"Edit Trade #{raw.get('id')}",
            timezone=services.config.get("timezone", "Australia/Brisbane"),
            initial=initial,
        )
        result = await self.app.push_screen_wait(form)
        if not result:
            return
        repo = services.repo
        txn_id = int(raw["id"])
        repo.update_transaction(
            txn_id,
            {
                "dt": result["dt"].isoformat(),
                "type": result["type"],
                "symbol": result["symbol"],
                "qty": float(result["qty"]),
                "price": float(result["price"]),
                "fees": float(result["fees"]),
                "broker_ref": result.get("broker_ref"),
                "notes": result.get("notes"),
                "exchange": result.get("exchange"),
            },
        )
        services.portfolio.rebuild_state()
        self._dirty = True
        services.actionables.evaluate_rules(include_snoozed=True)
        self.refresh_view()
        show_toast(self.app, "Trade updated", severity="success")

    def handle_delete(self) -> None:
        services = self.services
        if services is None:
            return
        selected = self.table.get_selected_row()
        if not selected:
            show_toast(self.app, "Select a trade to delete", severity="warning")
            return
        txn_id = int(selected.get("id"))
        repo = services.repo
        repo.delete_transaction(txn_id)
        services.portfolio.rebuild_state()
        self._dirty = True
        services.actionables.evaluate_rules(include_snoozed=True)
        self.refresh_view()
        show_toast(self.app, f"Deleted trade #{txn_id}", severity="warning")


__all__ = ["TradesView"]
