from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from portfolio_tool.config import Config
from portfolio_tool.data import models


@dataclass
class ActionableData:
    type: str
    symbol: str | None
    message: str
    due_at: dt.datetime | None = None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def generate_cgt_actionables(
    session: Session, cfg: Config, lots: Iterable[models.Lot]
) -> List[ActionableData]:
    window = dt.timedelta(days=cfg.rule_thresholds.cgt_window_days)
    today = _now().date()
    actionables: list[ActionableData] = []
    for lot in lots:
        if lot.qty_remaining <= 0:
            continue
        threshold = lot.threshold_date
        if threshold >= today and (threshold - today) <= window:
            message = f"Lot {lot.id} in {lot.symbol} eligible for CGT discount on {threshold.isoformat()}"
            due_at = dt.datetime.combine(threshold, dt.time.min, tzinfo=dt.timezone.utc)
            actionables.append(
                ActionableData(
                    type="cgt_window",
                    symbol=lot.symbol,
                    message=message,
                    due_at=due_at,
                )
            )
    return actionables


def generate_overweight_actionables(positions: list[dict], cfg: Config) -> List[ActionableData]:
    actionables: list[ActionableData] = []
    for pos in positions:
        symbol = pos["symbol"] if isinstance(pos, dict) else pos.symbol
        weight = (pos.get("weight") if isinstance(pos, dict) else getattr(pos, "weight", None)) or Decimal("0")
        target = Decimal(str(cfg.target_weights.get(symbol, 0)))
        if target and weight > target + Decimal(str(cfg.rule_thresholds.overweight_band)):
            message = f"{symbol} weight {weight:.2%} exceeds target {target:.2%}"
            actionables.append(ActionableData(type="overweight", symbol=symbol, message=message))
    return actionables


def generate_concentration_actionables(positions: list[dict], cfg: Config) -> List[ActionableData]:
    if not positions:
        return []
    def _weight(p):
        if isinstance(p, dict):
            return p.get("weight", Decimal("0"))
        return getattr(p, "weight", Decimal("0")) or Decimal("0")

    top = max(positions, key=_weight)
    limit = Decimal(str(cfg.rule_thresholds.concentration_limit))
    weight = _weight(top)
    symbol = top["symbol"] if isinstance(top, dict) else top.symbol
    if weight > limit:
        message = f"{symbol} concentration {weight:.2%} exceeds limit {limit:.2%}"
        return [ActionableData(type="concentration", symbol=symbol, message=message)]
    return []


def generate_drawdown_actionables(positions: list[dict], cfg: Config) -> List[ActionableData]:
    threshold = Decimal(str(cfg.rule_thresholds.drawdown_pct))
    actionables: list[ActionableData] = []
    for pos in positions:
        unrealised_pct = pos.get("unrealised_pct") if isinstance(pos, dict) else getattr(pos, "unrealised_pct", None)
        if unrealised_pct is None:
            continue
        if unrealised_pct < Decimal("0") and abs(unrealised_pct) > threshold:
            symbol = pos["symbol"] if isinstance(pos, dict) else pos.symbol
            message = f"{symbol} drawdown {unrealised_pct:.2%} exceeds {threshold:.2%}"
            actionables.append(ActionableData(type="drawdown", symbol=symbol, message=message))
    return actionables


def generate_stale_note_actionables(session: Session, cfg: Config) -> List[ActionableData]:
    cutoff = _now() - dt.timedelta(days=cfg.rule_thresholds.stale_note_days)
    stmt = select(models.Trade).where(
        models.Trade.note.is_not(None),
        models.Trade.note != "",
        models.Trade.updated_at < cutoff,
    )
    actionables: list[ActionableData] = []
    for trade in session.scalars(stmt):
        message = f"Trade {trade.id} note stale since {trade.updated_at.date().isoformat()}"
        actionables.append(ActionableData(type="stale_note", symbol=trade.symbol, message=message))
    return actionables


def generate_all_actionables(
    session: Session, cfg: Config, positions: list[dict], lots: Iterable[models.Lot]
) -> List[ActionableData]:
    actionables: list[ActionableData] = []
    actionables.extend(generate_cgt_actionables(session, cfg, lots))
    actionables.extend(generate_overweight_actionables(positions, cfg))
    actionables.extend(generate_concentration_actionables(positions, cfg))
    actionables.extend(generate_drawdown_actionables(positions, cfg))
    actionables.extend(generate_stale_note_actionables(session, cfg))
    return actionables


__all__ = [
    "ActionableData",
    "generate_all_actionables",
    "generate_cgt_actionables",
    "generate_overweight_actionables",
    "generate_concentration_actionables",
    "generate_drawdown_actionables",
    "generate_stale_note_actionables",
]
