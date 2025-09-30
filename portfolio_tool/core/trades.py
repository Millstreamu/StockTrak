from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from portfolio_tool.config import Config
from portfolio_tool.core.lots import apply_disposal, match_disposal
from portfolio_tool.data import models, repo


@dataclass
class TradeInput:
    side: str
    symbol: str
    dt: dt.datetime
    qty: Decimal
    price: Decimal
    fees: Decimal
    exchange: str | None = None
    note: str | None = None


def record_trade(
    session: Session,
    cfg: Config,
    trade_input: TradeInput,
    match_method: str | None = None,
    specific_ids: Sequence[int] | None = None,
):
    side = trade_input.side.upper()
    symbol = trade_input.symbol.upper()
    trade = repo.create_trade(
        session,
        {
            "side": side,
            "symbol": symbol,
            "dt": trade_input.dt,
            "qty": trade_input.qty,
            "price": trade_input.price,
            "fees": trade_input.fees,
            "exchange": trade_input.exchange,
            "note": trade_input.note,
        },
    )
    if side == "BUY":
        fee_allocation = Decimal("0")
        if cfg.brokerage_allocation == "BUY":
            fee_allocation = trade_input.fees
        elif cfg.brokerage_allocation == "SPLIT":
            fee_allocation = trade_input.fees / 2
        tz = ZoneInfo(cfg.timezone)
        threshold_date = trade.dt.astimezone(tz).date() + dt.timedelta(days=365)
        lot = models.Lot(
            symbol=trade.symbol,
            acquired_at=trade.dt,
            qty_remaining=trade.qty,
            cost_base_total=trade.qty * trade.price + fee_allocation,
            threshold_date=threshold_date,
            trade_id=trade.id,
        )
        session.add(lot)
        session.flush()
    else:
        fee_allocation = Decimal("0")
        if cfg.brokerage_allocation == "SELL":
            fee_allocation = trade_input.fees
        elif cfg.brokerage_allocation == "SPLIT":
            fee_allocation = trade_input.fees / 2
        lots = repo.list_open_lots(session, symbol)
        if not lots:
            raise ValueError("No lots available to match SELL")
        method = (match_method or cfg.lot_matching).upper()
        lot_slices = match_disposal(lots, trade_input.qty, method, specific_ids)
        apply_disposal(
            session,
            lot_slices,
            sell_trade=trade,
            sell_qty=trade_input.qty,
            sell_price=trade_input.price,
            fees_alloc=fee_allocation,
            tz=cfg.timezone,
        )
    return trade


__all__ = ["TradeInput", "record_trade"]
