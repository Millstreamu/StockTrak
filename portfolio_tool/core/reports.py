"""Reporting helpers for portfolio snapshots and ledgers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Mapping, Sequence

from zoneinfo import ZoneInfo

from ..data.repo_base import BaseRepository
from .models import Lot, Position, PriceQuote
from .services import PortfolioService


def _ensure_dt(value: datetime | date | None, tz: ZoneInfo) -> datetime:
    if value is None:
        return datetime.now(tz=tz)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=tz)
    return datetime(value.year, value.month, value.day, tzinfo=tz)


def _parse_dt(value: str | None, tz: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


class ReportingService:
    """Produce serialisable reports from repository state."""

    def __init__(
        self,
        repo: BaseRepository,
        *,
        timezone: str = "Australia/Brisbane",
        base_currency: str = "AUD",
        portfolio_service: PortfolioService | None = None,
    ) -> None:
        self.repo = repo
        self.tz = ZoneInfo(timezone)
        self.base_currency = base_currency
        self.portfolio = portfolio_service or PortfolioService(
            repo,
            timezone=timezone,
        )

    # ------------------------------------------------------------------
    def positions_snapshot(
        self,
        asof: datetime | date | None,
        prices: Mapping[str, PriceQuote] | None,
    ) -> list[dict[str, object]]:
        asof_dt = _ensure_dt(asof, self.tz)
        prices = prices or {}
        positions: Sequence[Position] = self.portfolio.compute_positions(prices=prices)
        rows: list[dict[str, object]] = []
        total_mv = 0.0
        total_cost = 0.0
        for position in positions:
            cost_base = position.avg_cost * position.total_qty
            total_cost += cost_base
            quote = prices.get(position.symbol)
            row = {
                "report_asof": asof_dt,
                "base_currency": self.base_currency,
                "symbol": position.symbol,
                "quantity": position.total_qty,
                "avg_cost": position.avg_cost,
                "cost_base": cost_base,
                "price": quote.price if isinstance(quote, PriceQuote) else None,
                "price_source": quote.source if isinstance(quote, PriceQuote) else None,
                "price_asof": quote.asof if isinstance(quote, PriceQuote) else None,
                "price_stale": quote.stale if isinstance(quote, PriceQuote) else None,
                "market_value": position.mv,
                "weight_pct": (position.weight or 0.0) * 100 if position.weight is not None else None,
            }
            if position.mv is not None:
                total_mv += position.mv
            rows.append(row)
        if rows:
            rows.sort(key=lambda item: item["symbol"])
            rows.append(
                {
                    "report_asof": asof_dt,
                    "base_currency": self.base_currency,
                    "symbol": "TOTAL",
                    "quantity": sum(r["quantity"] for r in rows if isinstance(r.get("quantity"), (int, float))),
                    "avg_cost": None,
                    "cost_base": total_cost,
                    "price": None,
                    "price_source": None,
                    "price_asof": None,
                    "price_stale": None,
                    "market_value": total_mv,
                    "weight_pct": 100.0 if total_mv else None,
                }
            )
        return rows

    # ------------------------------------------------------------------
    def lots_ledger(self, symbol: str | None = None) -> list[dict[str, object]]:
        lots = self.repo.list_lots(symbol=symbol)
        rows: list[dict[str, object]] = []
        for lot_row in lots:
            lot = self._lot_from_row(lot_row)
            txn = self.repo.get_transaction(lot.source_txn_id) if lot.source_txn_id else None
            original_qty = float(txn["qty"]) if txn else lot.qty_remaining
            disposals = self.repo.list_disposals(lot_id=lot.lot_id) if lot.lot_id else []
            disposed_qty = sum(float(d["qty"]) for d in disposals)
            disposed_cost = sum(float(d["cost_base_alloc"]) for d in disposals)
            rows.append(
                {
                    "lot_id": lot.lot_id,
                    "symbol": lot.symbol,
                    "acquired_at": lot.acquired_at,
                    "threshold_date": lot.threshold_date,
                    "original_qty": original_qty,
                    "qty_remaining": lot.qty_remaining,
                    "qty_disposed": disposed_qty,
                    "cost_base_initial": lot.cost_base_total + disposed_cost,
                    "cost_base_remaining": lot.cost_base_total,
                    "status": "OPEN" if lot.qty_remaining > 0 else "CLOSED",
                    "source_txn_id": lot.source_txn_id,
                }
            )
        rows.sort(key=lambda item: (item["symbol"], item["acquired_at"]))
        return rows

    # ------------------------------------------------------------------
    def cgt_calendar(
        self,
        *,
        asof: datetime | date | None,
        window_days: int,
    ) -> list[dict[str, object]]:
        asof_dt = _ensure_dt(asof, self.tz)
        rows: list[dict[str, object]] = []
        for lot_row in self.repo.list_lots(only_open=True):
            threshold_raw = lot_row.get("threshold_date")
            if not threshold_raw:
                continue
            threshold_dt = _parse_dt(threshold_raw, self.tz)
            if threshold_dt is None:
                continue
            delta_days = (threshold_dt.date() - asof_dt.date()).days
            eligible = delta_days <= 0
            if delta_days <= window_days:
                rows.append(
                    {
                        "report_asof": asof_dt,
                        "window_days": window_days,
                        "symbol": lot_row["symbol"],
                        "lot_id": lot_row.get("lot_id"),
                        "acquired_at": _parse_dt(lot_row.get("acquired_at"), self.tz),
                        "threshold_date": threshold_dt,
                        "days_until": delta_days,
                        "eligible_for_discount": eligible,
                        "qty_remaining": lot_row.get("qty_remaining"),
                    }
                )
        rows.sort(key=lambda item: (item["threshold_date"], item["symbol"]))
        return rows

    # ------------------------------------------------------------------
    def trade_audit_log(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for txn in self.repo.list_transactions():
            disposals = (
                self.repo.list_disposals(sell_txn_id=txn["id"])
                if txn["type"] == "SELL"
                else []
            )
            proceeds = float(txn["qty"]) * float(txn["price"]) - float(txn.get("fees", 0.0))
            cost_base = sum(float(d["cost_base_alloc"]) for d in disposals)
            gain = sum(float(d["gain_loss"]) for d in disposals)
            rows.append(
                {
                    "txn_id": txn["id"],
                    "dt": datetime.fromisoformat(txn["dt"]),
                    "type": txn["type"],
                    "symbol": txn["symbol"],
                    "qty": float(txn["qty"]),
                    "price": float(txn["price"]),
                    "fees": float(txn.get("fees", 0.0)),
                    "proceeds": proceeds,
                    "cost_base": cost_base if disposals else None,
                    "gain_loss": gain if disposals else None,
                    "broker_ref": txn.get("broker_ref"),
                    "notes": txn.get("notes"),
                }
            )
        rows.sort(key=lambda item: (item["dt"], item["txn_id"]))
        return rows

    # ------------------------------------------------------------------
    def _lot_from_row(self, row: Mapping[str, object]) -> Lot:
        acquired_at = _parse_dt(row.get("acquired_at"), self.tz)
        threshold = _parse_dt(row.get("threshold_date"), self.tz)
        return Lot(
            lot_id=row.get("lot_id"),
            symbol=row["symbol"],
            acquired_at=acquired_at or datetime.now(tz=self.tz),
            qty_remaining=float(row.get("qty_remaining", 0.0)),
            cost_base_total=float(row.get("cost_base_total", 0.0)),
            threshold_date=threshold,
            source_txn_id=row.get("source_txn_id"),
        )


_CURRENT_ENGINE: ReportingService | None = None


def set_reporting_engine(engine: ReportingService | None) -> None:
    global _CURRENT_ENGINE
    _CURRENT_ENGINE = engine


def positions_report(asof, prices: dict) -> list:
    if _CURRENT_ENGINE is None:
        raise RuntimeError("Reporting engine not configured")
    return _CURRENT_ENGINE.positions_snapshot(asof, prices)


__all__ = [
    "ReportingService",
    "positions_report",
    "set_reporting_engine",
]
