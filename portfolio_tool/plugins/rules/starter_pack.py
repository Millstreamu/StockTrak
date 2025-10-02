"""Starter pack rule implementations."""
from __future__ import annotations

from typing import Iterable, List

from ...core.rules import ActionableCandidate, RuleContext, RuleCallable


def cgt_window_rule(ctx: RuleContext) -> Iterable[ActionableCandidate]:
    window = int(ctx.thresholds.get("cgt_window_days", 60))
    results: List[ActionableCandidate] = []
    for lot in ctx.lots:
        threshold = lot.get("threshold_date")
        lot_id = lot.get("lot_id")
        if not threshold or lot_id is None:
            continue
        days = (threshold.date() - ctx.asof.date()).days
        if 0 <= days <= window:
            symbol = str(lot["symbol"])
            message = (
                f"{symbol} lot {lot_id} reaches CGT discount in {days} days"
                if days
                else f"{symbol} lot {lot_id} is CGT discount eligible"
            )
            results.append(
                ActionableCandidate(
                    type="CGT_WINDOW",
                    symbol=symbol,
                    message=message,
                    context=f"lot:{lot_id}",
                )
            )
    return results


def weight_rules(ctx: RuleContext) -> Iterable[ActionableCandidate]:
    band = float(ctx.thresholds.get("overweight_band", 0.02))
    concentration_limit = float(ctx.thresholds.get("concentration_limit", 0.25))
    results: List[ActionableCandidate] = []
    for row in ctx.positions:
        symbol = str(row.get("symbol"))
        weight_pct = row.get("weight_pct")
        if symbol == "TOTAL" or weight_pct is None:
            continue
        target = ctx.target_weights.get(symbol.upper())
        weight = float(weight_pct) / 100.0
        if target is not None:
            if weight > target + band:
                message = (
                    f"{symbol} weight {weight:.2%} exceeds target {target:.2%}"
                )
                results.append(
                    ActionableCandidate(
                        type="OVERWEIGHT",
                        symbol=symbol,
                        message=message,
                        context=f"target:{symbol.upper()}",
                    )
                )
            elif weight < target - band:
                message = (
                    f"{symbol} weight {weight:.2%} below target {target:.2%}"
                )
                results.append(
                    ActionableCandidate(
                        type="UNDERWEIGHT",
                        symbol=symbol,
                        message=message,
                        context=f"target:{symbol.upper()}",
                    )
                )
        if weight > concentration_limit:
            results.append(
                ActionableCandidate(
                    type="CONCENTRATION",
                    symbol=symbol,
                    message=(
                        f"{symbol} concentration {weight:.2%} exceeds limit {concentration_limit:.2%}"
                    ),
                    context=f"concentration:{symbol.upper()}",
                )
            )
    return results


def trailing_stop_rule(ctx: RuleContext) -> Iterable[ActionableCandidate]:
    results: List[ActionableCandidate] = []
    for row in ctx.positions:
        symbol = str(row.get("symbol"))
        if symbol == "TOTAL":
            continue
        transactions = ctx.transactions.get(symbol, [])
        has_stop = False
        for txn in transactions:
            notes = str(txn.get("notes") or "").lower()
            if "stop" in notes:
                has_stop = True
                break
        if not has_stop:
            results.append(
                ActionableCandidate(
                    type="TRAILING_STOP",
                    symbol=symbol,
                    message=f"Add or update trailing stop for {symbol}",
                    context=f"trailing:{symbol.upper()}",
                )
            )
    return results


def unrealised_loss_rule(ctx: RuleContext) -> Iterable[ActionableCandidate]:
    threshold = float(ctx.thresholds.get("loss_threshold_pct", -0.15))
    results: List[ActionableCandidate] = []
    for row in ctx.positions:
        symbol = str(row.get("symbol"))
        if symbol == "TOTAL":
            continue
        cost_base = row.get("cost_base")
        market_value = row.get("market_value")
        if not cost_base or not market_value:
            continue
        cost = float(cost_base)
        mv = float(market_value)
        if cost <= 0:
            continue
        pnl_pct = (mv - cost) / cost
        if pnl_pct <= threshold:
            results.append(
                ActionableCandidate(
                    type="UNREALISED_LOSS",
                    symbol=symbol,
                    message=(
                        f"{symbol} unrealised loss {pnl_pct:.1%} (MV {mv:,.2f} < cost {cost:,.2f})"
                    ),
                    context=f"loss:{symbol.upper()}",
                )
            )
    return results


def stale_price_rule(ctx: RuleContext) -> Iterable[ActionableCandidate]:
    results: List[ActionableCandidate] = []
    for quote in ctx.quotes.values():
        if not quote.stale:
            continue
        symbol = quote.symbol
        results.append(
            ActionableCandidate(
                type="STALE_PRICE",
                symbol=symbol,
                message=f"Price for {symbol} is stale (as of {quote.asof.isoformat()})",
                context=f"stale:{symbol.upper()}",
            )
        )
    return results


_RULES: tuple[RuleCallable, ...] = (
    cgt_window_rule,
    weight_rules,
    trailing_stop_rule,
    unrealised_loss_rule,
    stale_price_rule,
)


def get_rules() -> tuple[RuleCallable, ...]:
    return _RULES


__all__ = [
    "cgt_window_rule",
    "weight_rules",
    "trailing_stop_rule",
    "unrealised_loss_rule",
    "stale_price_rule",
    "get_rules",
]
