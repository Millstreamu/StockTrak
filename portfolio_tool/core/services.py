"""Domain services that orchestrate repository interactions."""
from __future__ import annotations

from datetime import datetime

from zoneinfo import ZoneInfo

from ..data.repo_base import BaseRepository
from .cgt import CGTEngine, cgt_threshold
from .lots import LotEngine, LotMatchingError
from .models import Lot, Position, PriceQuote, Transaction


class PortfolioService:
    """Service responsible for recording trades and producing positions."""

    def __init__(
        self,
        repo: BaseRepository,
        *,
        timezone: str = "Australia/Brisbane",
        lot_matching: str = "FIFO",
        brokerage_allocation: str = "BUY",
    ) -> None:
        self.repo = repo
        self.timezone = timezone
        self.lot_engine = LotEngine(lot_matching)
        self.cgt_engine = CGTEngine(timezone)
        self.brokerage_allocation = brokerage_allocation.upper()

    # ------------------------------------------------------------------
    def record_trade(
        self,
        txn: Transaction,
        *,
        specific_lots: dict[int, float] | None = None,
    ) -> int:
        """Persist a transaction and update lot/disposal state."""

        txn_dict = {
            "dt": txn.dt.isoformat(),
            "type": txn.type,
            "symbol": txn.symbol,
            "qty": txn.qty,
            "price": txn.price,
            "fees": txn.fees,
            "broker_ref": txn.broker_ref,
            "notes": txn.notes,
            "exchange": txn.exchange,
        }
        txn_id = self.repo.add_transaction(txn_dict)
        txn.id = txn_id

        if txn.type == "BUY" or txn.type == "DRP":
            self._record_buy(txn)
        elif txn.type == "SELL":
            self._record_sell(txn, specific_lots=specific_lots)
        else:
            raise ValueError(f"Unsupported transaction type: {txn.type}")
        return txn_id

    # ------------------------------------------------------------------
    def _record_buy(self, txn: Transaction) -> None:
        tzinfo = ZoneInfo(self.timezone)
        threshold = cgt_threshold(txn.dt, self.timezone)
        base_cost = txn.qty * txn.price
        if self.brokerage_allocation in {"BUY", "SPLIT"}:
            base_cost += txn.fees
        lot = Lot(
            lot_id=None,
            symbol=txn.symbol,
            acquired_at=txn.dt.astimezone(tzinfo),
            qty_remaining=txn.qty,
            cost_base_total=base_cost,
            threshold_date=threshold,
            source_txn_id=txn.id,
        )
        lot_record = {
            "symbol": lot.symbol,
            "acquired_at": lot.acquired_at.isoformat(),
            "qty_remaining": lot.qty_remaining,
            "cost_base_total": lot.cost_base_total,
            "threshold_date": lot.threshold_date.isoformat() if lot.threshold_date else None,
            "source_txn_id": lot.source_txn_id,
        }
        lot_id = self.repo.add_lot(lot_record)
        lot.lot_id = lot_id

    # ------------------------------------------------------------------
    def _record_sell(
        self,
        txn: Transaction,
        *,
        specific_lots: dict[int, float] | None,
    ) -> None:
        open_lots = [
            self._lot_from_row(row)
            for row in self.repo.list_lots(symbol=txn.symbol, only_open=True)
        ]
        try:
            matches = self.lot_engine.match(open_lots, txn.qty, specific_lots)
        except LotMatchingError as exc:
            raise ValueError(str(exc)) from exc

        sell_fee = txn.fees if self.brokerage_allocation in {"SELL", "SPLIT"} else 0.0
        slices = self.cgt_engine.slice_disposal(txn, matches, sell_fee)

        for (lot, qty), disposal in zip(matches, slices):
            if lot.lot_id is None:
                continue
            remaining_qty = lot.qty_remaining - qty
            remaining_cost = lot.cost_base_total - disposal.cost_base_alloc
            if remaining_qty < 0:
                remaining_qty = 0
            if remaining_cost < 0 and remaining_cost > -1e-9:
                remaining_cost = 0.0
            self.repo.update_lot(
                lot.lot_id,
                {
                    "qty_remaining": remaining_qty,
                    "cost_base_total": remaining_cost,
                },
            )
            self.repo.add_disposal(
                {
                    "sell_txn_id": txn.id,
                    "lot_id": lot.lot_id,
                    "qty": disposal.qty,
                    "proceeds": disposal.proceeds,
                    "cost_base_alloc": disposal.cost_base_alloc,
                    "gain_loss": disposal.gain_loss,
                    "eligible_for_discount": int(disposal.eligible_for_discount),
                }
            )

    # ------------------------------------------------------------------
    def compute_positions(
        self,
        *,
        asof: datetime | None = None,
        prices: dict[str, PriceQuote | float] | None = None,
    ) -> list[Position]:
        lots = [self._lot_from_row(row) for row in self.repo.list_lots(only_open=True)]
        aggregates: dict[str, tuple[float, float]] = {}
        for lot in lots:
            qty, cost = aggregates.get(lot.symbol, (0.0, 0.0))
            aggregates[lot.symbol] = (qty + lot.qty_remaining, cost + lot.cost_base_total)

        price_lookup: dict[str, float | None] = {}
        if prices:
            for symbol, quote in prices.items():
                if isinstance(quote, PriceQuote):
                    price_lookup[symbol] = quote.price
                else:
                    price_lookup[symbol] = float(quote)

        positions: list[Position] = []
        total_mv = 0.0
        mv_by_symbol: dict[str, float] = {}
        for symbol, (qty, cost) in aggregates.items():
            avg_cost = cost / qty if qty else 0.0
            price = price_lookup.get(symbol)
            mv = price * qty if price is not None else None
            if mv is not None:
                total_mv += mv
                mv_by_symbol[symbol] = mv
            positions.append(
                Position(
                    symbol=symbol,
                    total_qty=qty,
                    avg_cost=avg_cost,
                    mv=mv,
                    weight=None,
                )
            )

        if total_mv > 0:
            for position in positions:
                mv = mv_by_symbol.get(position.symbol)
                position.weight = (mv / total_mv) if mv is not None else None

        positions.sort(key=lambda pos: pos.symbol)
        return positions

    # ------------------------------------------------------------------
    def rebuild_state(self) -> None:
        """Recompute lot and disposal state from persisted transactions."""

        tzinfo = ZoneInfo(self.timezone)
        transactions = self.repo.list_transactions(order="asc")
        if not transactions:
            for lot in list(self.repo.list_lots()):
                lot_id = lot.get("lot_id")
                if lot_id is not None:
                    self.repo.delete_lot(int(lot_id))
            return

        specific_maps: dict[int, dict[int, float]] = {}
        for row in transactions:
            if str(row.get("type")).upper() != "SELL":
                continue
            sell_id = int(row["id"])
            disposals = self.repo.list_disposals(sell_txn_id=sell_id)
            if not disposals:
                continue
            mapping: dict[int, float] = {}
            for disp in disposals:
                lot_id = disp.get("lot_id")
                qty = disp.get("qty")
                if lot_id is None or qty is None:
                    continue
                mapping[int(lot_id)] = float(qty)
            if mapping:
                specific_maps[sell_id] = mapping

        for row in list(self.repo.list_lots()):
            lot_id = row.get("lot_id")
            if lot_id is not None:
                self.repo.delete_lot(int(lot_id))
        for row in transactions:
            if str(row.get("type")).upper() == "SELL":
                self.repo.delete_disposals_for_sell(int(row["id"]))

        for row in transactions:
            txn = Transaction(
                id=int(row["id"]),
                dt=datetime.fromisoformat(row["dt"]).astimezone(tzinfo),
                type=row["type"],
                symbol=row["symbol"],
                qty=float(row["qty"]),
                price=float(row["price"]),
                fees=float(row.get("fees", 0.0)),
                broker_ref=row.get("broker_ref"),
                notes=row.get("notes"),
                exchange=row.get("exchange"),
            )
            if txn.type in {"BUY", "DRP"}:
                self._record_buy(txn)
            elif txn.type == "SELL":
                specific = specific_maps.get(txn.id or -1)
                self._record_sell(txn, specific_lots=specific)
            else:
                raise ValueError(f"Unsupported transaction type: {txn.type}")

    # ------------------------------------------------------------------
    def _lot_from_row(self, row: dict) -> Lot:
        tzinfo = ZoneInfo(self.timezone)
        acquired_at = datetime.fromisoformat(row["acquired_at"]).astimezone(tzinfo)
        threshold_raw = row.get("threshold_date")
        threshold = (
            datetime.fromisoformat(threshold_raw).astimezone(tzinfo)
            if threshold_raw
            else None
        )
        return Lot(
            lot_id=row.get("lot_id"),
            symbol=row["symbol"],
            acquired_at=acquired_at,
            qty_remaining=row["qty_remaining"],
            cost_base_total=row["cost_base_total"],
            threshold_date=threshold,
            source_txn_id=row.get("source_txn_id"),
        )


__all__ = ["PortfolioService"]
