"""Portable JSON-backed repository implementation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .repo_base import BaseRepository, RepositoryError, normalise_order

_DEFAULT_STATE = {
    "meta": {
        "next_ids": {
            "transactions": 1,
            "lots": 1,
            "disposals": 1,
            "actionables": 1,
        }
    },
    "transactions": [],
    "lots": [],
    "disposals": [],
    "price_cache": {},
    "actionables": [],
}


class JSONRepository(BaseRepository):
    """Repository that persists state in a JSON document."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_state(_DEFAULT_STATE)
        self._state = self._read_state()

    # ------------------------------------------------------------------
    def close(self) -> None:
        self._write_state(self._state)

    # ------------------------------------------------------------------
    def _read_state(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise RepositoryError(f"Invalid JSON repository: {exc}") from exc

    def _write_state(self, state: Mapping[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)

    def _next_id(self, key: str) -> int:
        counter = self._state["meta"]["next_ids"]
        value = counter[key]
        counter[key] = value + 1
        return value

    def _persist(self) -> None:
        self._write_state(self._state)

    # --- transactions --------------------------------------------------
    def add_transaction(self, txn: Mapping[str, Any]) -> int:
        txn_id = self._next_id("transactions")
        record = {"id": txn_id, **txn}
        self._state["transactions"].append(record)
        self._persist()
        return txn_id

    def get_transaction(self, txn_id: int) -> dict[str, Any] | None:
        for row in self._state["transactions"]:
            if row["id"] == txn_id:
                return row.copy()
        return None

    def list_transactions(
        self,
        *,
        symbol: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str = "asc",
    ) -> list[dict[str, Any]]:
        order = normalise_order(order)
        rows = [row.copy() for row in self._state["transactions"]]
        if symbol:
            rows = [row for row in rows if row["symbol"] == symbol]
        rows.sort(key=lambda r: (r["dt"], r["id"]), reverse=order == "desc")
        if limit is not None:
            rows = rows[offset : offset + limit]
        return rows

    def update_transaction(self, txn_id: int, updates: Mapping[str, Any]) -> None:
        for row in self._state["transactions"]:
            if row["id"] == txn_id:
                row.update(updates)
                self._persist()
                return
        raise RepositoryError(f"Transaction {txn_id} not found")

    def delete_transaction(self, txn_id: int) -> None:
        rows = self._state["transactions"]
        for idx, row in enumerate(rows):
            if row["id"] == txn_id:
                rows.pop(idx)
                self._persist()
                return

    # --- lots ----------------------------------------------------------
    def add_lot(self, lot: Mapping[str, Any]) -> int:
        lot_id = self._next_id("lots")
        record = {"lot_id": lot_id, **lot}
        self._state["lots"].append(record)
        self._persist()
        return lot_id

    def update_lot(self, lot_id: int, updates: Mapping[str, Any]) -> None:
        for row in self._state["lots"]:
            if row["lot_id"] == lot_id:
                row.update(updates)
                self._persist()
                return
        raise RepositoryError(f"Lot {lot_id} not found")

    def list_lots(
        self,
        *,
        symbol: str | None = None,
        only_open: bool = False,
    ) -> list[dict[str, Any]]:
        rows = [row.copy() for row in self._state["lots"]]
        if symbol:
            rows = [row for row in rows if row["symbol"] == symbol]
        if only_open:
            rows = [row for row in rows if row.get("qty_remaining", 0) > 0]
        rows.sort(key=lambda r: (r.get("acquired_at"), r["lot_id"]))
        return rows

    def delete_lot(self, lot_id: int) -> None:
        rows = self._state["lots"]
        for idx, row in enumerate(rows):
            if row["lot_id"] == lot_id:
                rows.pop(idx)
                self._persist()
                return

    # --- disposals -----------------------------------------------------
    def add_disposal(self, disposal: Mapping[str, Any]) -> int:
        disp_id = self._next_id("disposals")
        record = {"id": disp_id, **disposal}
        self._state["disposals"].append(record)
        self._persist()
        return disp_id

    def list_disposals(
        self,
        *,
        sell_txn_id: int | None = None,
        lot_id: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = [row.copy() for row in self._state["disposals"]]
        if sell_txn_id is not None:
            rows = [row for row in rows if row.get("sell_txn_id") == sell_txn_id]
        if lot_id is not None:
            rows = [row for row in rows if row.get("lot_id") == lot_id]
        rows.sort(key=lambda r: r["id"])
        return rows

    def delete_disposals_for_sell(self, sell_txn_id: int) -> None:
        rows = self._state["disposals"]
        self._state["disposals"] = [
            row for row in rows if row.get("sell_txn_id") != sell_txn_id
        ]
        self._persist()

    # --- price cache ---------------------------------------------------
    def upsert_price(self, record: Mapping[str, Any]) -> None:
        symbol = record["symbol"]
        self._state["price_cache"][symbol] = dict(record)
        self._persist()

    def get_prices(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        return {
            symbol: self._state["price_cache"][symbol].copy()
            for symbol in symbols
            if symbol in self._state["price_cache"]
        }

    def purge_price(self, symbol: str) -> None:
        self._state["price_cache"].pop(symbol, None)
        self._persist()

    # --- actionables ---------------------------------------------------
    def add_actionable(self, actionable: Mapping[str, Any]) -> int:
        actionable_id = self._next_id("actionables")
        record = {"id": actionable_id, **actionable}
        self._state["actionables"].append(record)
        self._persist()
        return actionable_id

    def update_actionable(self, actionable_id: int, updates: Mapping[str, Any]) -> None:
        for row in self._state["actionables"]:
            if row["id"] == actionable_id:
                row.update(updates)
                self._persist()
                return
        raise RepositoryError(f"Actionable {actionable_id} not found")

    def list_actionables(
        self,
        *,
        status: str | None = None,
        include_snoozed: bool = True,
    ) -> list[dict[str, Any]]:
        rows = [row.copy() for row in self._state["actionables"]]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if not include_snoozed:
            rows = [row for row in rows if row.get("snoozed_until") in (None, "")]
        rows.sort(key=lambda r: r["created_at"])
        return rows


__all__ = ["JSONRepository"]
