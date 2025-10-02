"""SQLite-backed repository implementation."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from .repo_base import BaseRepository, RepositoryError, normalise_order

MIGRATIONS_DIR = Path(__file__).with_suffix("").parent / "migrations"


class SQLiteRepository(BaseRepository):
    """Repository backed by a SQLite database file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._apply_migrations()

    # ------------------------------------------------------------------
    def close(self) -> None:
        if getattr(self, "_conn", None) is not None:
            self._conn.close()

    # ------------------------------------------------------------------
    def _apply_migrations(self) -> None:
        conn = self._conn
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY);"
        )
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations;")
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem.split("_")[0]
            if version in applied:
                continue
            sql = path.read_text()
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?);", (version,)
            )
        conn.commit()

    # ------------------------------------------------------------------
    def _execute(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        try:
            cur = self._conn.execute(query, params)
            self._conn.commit()
            return cur
        except sqlite3.DatabaseError as exc:  # pragma: no cover - defensive
            raise RepositoryError(str(exc)) from exc

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self._execute(query, params)
        return [dict(row) for row in cur.fetchall()]

    # --- transactions --------------------------------------------------
    def add_transaction(self, txn: Mapping[str, Any]) -> int:
        columns = ", ".join(txn.keys())
        placeholders = ", ".join(["?"] * len(txn))
        cur = self._execute(
            f"INSERT INTO transactions ({columns}) VALUES ({placeholders});",
            tuple(txn.values()),
        )
        return int(cur.lastrowid)

    def get_transaction(self, txn_id: int) -> dict[str, Any] | None:
        cur = self._execute(
            "SELECT * FROM transactions WHERE id = ?;", (txn_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_transactions(
        self,
        *,
        symbol: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str = "asc",
    ) -> list[dict[str, Any]]:
        order = normalise_order(order)
        query = "SELECT * FROM transactions"
        params: list[Any] = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += f" ORDER BY dt {order.upper()}"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        return self._fetchall(query + ";", tuple(params))

    def update_transaction(self, txn_id: int, updates: Mapping[str, Any]) -> None:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [txn_id]
        self._execute(
            f"UPDATE transactions SET {assignments} WHERE id = ?;", tuple(params)
        )

    def delete_transaction(self, txn_id: int) -> None:
        self._execute("DELETE FROM transactions WHERE id = ?;", (txn_id,))

    # --- lots ----------------------------------------------------------
    def add_lot(self, lot: Mapping[str, Any]) -> int:
        columns = ", ".join(lot.keys())
        placeholders = ", ".join(["?"] * len(lot))
        cur = self._execute(
            f"INSERT INTO lots ({columns}) VALUES ({placeholders});",
            tuple(lot.values()),
        )
        return int(cur.lastrowid)

    def update_lot(self, lot_id: int, updates: Mapping[str, Any]) -> None:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [lot_id]
        self._execute(f"UPDATE lots SET {assignments} WHERE lot_id = ?;", tuple(params))

    def list_lots(
        self,
        *,
        symbol: str | None = None,
        only_open: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM lots"
        clauses: list[str] = []
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        if only_open:
            clauses.append("qty_remaining > 0")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY acquired_at ASC, lot_id ASC;"
        return self._fetchall(query, tuple(params))

    def delete_lot(self, lot_id: int) -> None:
        self._execute("DELETE FROM lots WHERE lot_id = ?;", (lot_id,))

    def aggregate_open_lots(self) -> list[dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT symbol,
                   SUM(qty_remaining) AS total_qty,
                   SUM(cost_base_total) AS total_cost
            FROM lots
            WHERE qty_remaining > 0
            GROUP BY symbol
            ORDER BY symbol ASC;
            """
        )
        aggregates: list[dict[str, Any]] = []
        for row in rows:
            aggregates.append(
                {
                    "symbol": row["symbol"],
                    "total_qty": float(row.get("total_qty") or 0.0),
                    "total_cost": float(row.get("total_cost") or 0.0),
                }
            )
        return aggregates

    # --- disposals -----------------------------------------------------
    def add_disposal(self, disposal: Mapping[str, Any]) -> int:
        columns = ", ".join(disposal.keys())
        placeholders = ", ".join(["?"] * len(disposal))
        cur = self._execute(
            f"INSERT INTO disposals ({columns}) VALUES ({placeholders});",
            tuple(disposal.values()),
        )
        return int(cur.lastrowid)

    def list_disposals(
        self,
        *,
        sell_txn_id: int | None = None,
        lot_id: int | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM disposals"
        clauses: list[str] = []
        params: list[Any] = []
        if sell_txn_id is not None:
            clauses.append("sell_txn_id = ?")
            params.append(sell_txn_id)
        if lot_id is not None:
            clauses.append("lot_id = ?")
            params.append(lot_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id ASC;"
        return self._fetchall(query, tuple(params))

    def delete_disposals_for_sell(self, sell_txn_id: int) -> None:
        self._execute("DELETE FROM disposals WHERE sell_txn_id = ?;", (sell_txn_id,))

    # --- price cache ---------------------------------------------------
    def upsert_price(self, record: Mapping[str, Any]) -> None:
        columns = list(record.keys())
        placeholders = ", ".join(["?"] * len(columns))
        assignments = ", ".join(f"{col} = excluded.{col}" for col in columns if col != "symbol")
        self._execute(
            f"""
            INSERT INTO price_cache ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(symbol) DO UPDATE SET {assignments};
            """,
            tuple(record[col] for col in columns),
        )

    def get_prices(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        sym_list = list(symbols)
        if not sym_list:
            return {}
        placeholders = ", ".join(["?"] * len(sym_list))
        rows = self._fetchall(
            f"SELECT * FROM price_cache WHERE symbol IN ({placeholders});",
            tuple(sym_list),
        )
        return {row["symbol"]: row for row in rows}

    def purge_price(self, symbol: str) -> None:
        self._execute("DELETE FROM price_cache WHERE symbol = ?;", (symbol,))

    # --- actionables ---------------------------------------------------
    def add_actionable(self, actionable: Mapping[str, Any]) -> int:
        columns = ", ".join(actionable.keys())
        placeholders = ", ".join(["?"] * len(actionable))
        cur = self._execute(
            f"INSERT INTO actionables ({columns}) VALUES ({placeholders});",
            tuple(actionable.values()),
        )
        return int(cur.lastrowid)

    def update_actionable(self, actionable_id: int, updates: Mapping[str, Any]) -> None:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [actionable_id]
        self._execute(
            f"UPDATE actionables SET {assignments} WHERE id = ?;", tuple(params)
        )

    def list_actionables(
        self,
        *,
        status: str | None = None,
        include_snoozed: bool = True,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM actionables"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if not include_snoozed:
            clauses.append("snoozed_until IS NULL")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC;"
        return self._fetchall(query, tuple(params))


__all__ = ["SQLiteRepository"]
