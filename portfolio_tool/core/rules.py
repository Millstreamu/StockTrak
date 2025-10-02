"""Rules engine and actionable management."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterable, Mapping, Sequence

from zoneinfo import ZoneInfo

from ..data.repo_base import BaseRepository
from .models import Actionable, PriceQuote
from .reports import ReportingService
from .services import PortfolioService


@dataclass(slots=True)
class ActionableCandidate:
    """Result emitted by a rule evaluation."""

    type: str
    message: str
    symbol: str | None = None
    context: str | None = None


@dataclass(slots=True)
class RuleContext:
    """Context passed into rule callables."""

    asof: datetime
    positions: Sequence[dict[str, object]]
    lots: Sequence[dict[str, object]]
    quotes: Mapping[str, PriceQuote]
    transactions: Mapping[str, Sequence[dict[str, object]]]
    target_weights: Mapping[str, float]
    thresholds: Mapping[str, float]
    timezone: ZoneInfo


RuleCallable = Callable[[RuleContext], Iterable[ActionableCandidate]]


class ActionableService:
    """Evaluate rule packs and manage actionable persistence."""

    def __init__(
        self,
        repo: BaseRepository,
        *,
        portfolio_service: PortfolioService,
        reporting_service: ReportingService,
        pricing_service,
        timezone: str = "Australia/Brisbane",
        target_weights: Mapping[str, float] | None = None,
        rule_thresholds: Mapping[str, float] | None = None,
        rules: Sequence[RuleCallable] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo = repo
        self.portfolio = portfolio_service
        self.reporting = reporting_service
        self.pricing = pricing_service
        self.tz = ZoneInfo(timezone)
        self.target_weights = {
            key.upper(): float(value) for key, value in (target_weights or {}).items()
        }
        self.thresholds = {key: float(value) for key, value in (rule_thresholds or {}).items()}
        self._now = now_fn or (lambda: datetime.now(tz=self.tz))
        if rules is None:
            from ..plugins.rules import get_rules

            rules = get_rules()
        self.rules = list(rules)

    # ------------------------------------------------------------------
    def evaluate_rules(self, include_snoozed: bool = True) -> list[Actionable]:
        """Run configured rules and update persisted actionables."""

        asof = self._now()
        symbols = self._open_symbols()
        quotes = self.pricing.get_cached(symbols)
        positions = [
            row
            for row in self.reporting.positions_snapshot(asof, quotes)
            if row.get("symbol") != "TOTAL"
        ]
        lots = self._load_lots()
        transactions = self._load_transactions(symbols)
        context = RuleContext(
            asof=asof,
            positions=positions,
            lots=lots,
            quotes=quotes,
            transactions=transactions,
            target_weights=self.target_weights,
            thresholds=self.thresholds,
            timezone=self.tz,
        )
        candidates: dict[str, ActionableCandidate] = {}
        for rule in self.rules:
            for candidate in rule(context):
                key = self._candidate_key(candidate)
                candidates[key] = candidate

        existing = {
            self._candidate_key(self._actionable_from_row(row)): row
            for row in self.repo.list_actionables(include_snoozed=True)
        }

        updated_ids: set[int] = set()
        for key, candidate in candidates.items():
            row = existing.get(key)
            if row:
                actionable = self._actionable_from_row(row)
                status = actionable.status
                snoozed_until = actionable.snoozed_until
                if status == "SNOOZE" and snoozed_until and snoozed_until > asof:
                    new_status = "SNOOZE"
                else:
                    new_status = "OPEN"
                    snoozed_until = None
                updates = {
                    "message": candidate.message,
                    "symbol": candidate.symbol,
                    "context": candidate.context,
                    "status": new_status,
                    "updated_at": asof.isoformat(),
                    "snoozed_until": snoozed_until.isoformat() if snoozed_until else None,
                }
                self.repo.update_actionable(actionable.id, updates)
                updated_ids.add(actionable.id)
            else:
                payload = {
                    "type": candidate.type,
                    "symbol": candidate.symbol,
                    "message": candidate.message,
                    "status": "OPEN",
                    "created_at": asof.isoformat(),
                    "updated_at": asof.isoformat(),
                    "snoozed_until": None,
                    "context": candidate.context,
                }
                actionable_id = self.repo.add_actionable(payload)
                updated_ids.add(actionable_id)

        for row in existing.values():
            actionable = self._actionable_from_row(row)
            if actionable.id not in updated_ids and actionable.status == "OPEN":
                self.repo.update_actionable(
                    actionable.id,
                    {
                        "status": "DONE",
                        "updated_at": asof.isoformat(),
                        "snoozed_until": None,
                    },
                )

        return self.list_actionables(status=None, include_snoozed=include_snoozed)

    # ------------------------------------------------------------------
    def list_actionables(
        self, *, status: str | None = None, include_snoozed: bool = True
    ) -> list[Actionable]:
        rows = self.repo.list_actionables(status=status, include_snoozed=include_snoozed)
        return [self._actionable_from_row(row) for row in rows]

    # ------------------------------------------------------------------
    def complete(self, actionable_id: int) -> None:
        asof = self._now()
        self.repo.update_actionable(
            actionable_id,
            {
                "status": "DONE",
                "updated_at": asof.isoformat(),
                "snoozed_until": None,
            },
        )

    # ------------------------------------------------------------------
    def snooze(self, actionable_id: int, days: int) -> None:
        if days <= 0:
            raise ValueError("Snooze days must be positive")
        asof = self._now()
        snoozed_until = asof + timedelta(days=days)
        self.repo.update_actionable(
            actionable_id,
            {
                "status": "SNOOZE",
                "updated_at": asof.isoformat(),
                "snoozed_until": snoozed_until.isoformat(),
            },
        )

    # ------------------------------------------------------------------
    def _candidate_key(self, candidate: ActionableCandidate | Actionable) -> str:
        symbol = (candidate.symbol or "").upper()
        context = candidate.context or ""
        return f"{candidate.type}|{symbol}|{context}"

    # ------------------------------------------------------------------
    def _open_symbols(self) -> list[str]:
        rows = self.repo.list_lots(only_open=True)
        return sorted({row["symbol"] for row in rows})

    # ------------------------------------------------------------------
    def _load_lots(self) -> list[dict[str, object]]:
        rows = self.repo.list_lots(only_open=True)
        result: list[dict[str, object]] = []
        for row in rows:
            result.append(
                {
                    **row,
                    "acquired_at": self._parse_dt(row.get("acquired_at")),
                    "threshold_date": self._parse_dt(row.get("threshold_date")),
                    "qty_remaining": float(row.get("qty_remaining", 0.0)),
                }
            )
        return result

    # ------------------------------------------------------------------
    def _load_transactions(
        self, symbols: Sequence[str]
    ) -> dict[str, Sequence[dict[str, object]]]:
        mapping: dict[str, Sequence[dict[str, object]]] = {}
        for symbol in symbols:
            rows = self.repo.list_transactions(symbol=symbol)
            mapping[symbol] = rows
        return mapping

    # ------------------------------------------------------------------
    def _actionable_from_row(self, row: Mapping[str, object]) -> Actionable:
        return Actionable(
            id=int(row.get("id")),
            type=str(row.get("type")),
            symbol=row.get("symbol"),
            message=str(row.get("message")),
            status=str(row.get("status", "OPEN")).upper(),
            created_at=self._parse_dt(row.get("created_at")) or self._now(),
            updated_at=self._parse_dt(row.get("updated_at")) or self._now(),
            snoozed_until=self._parse_dt(row.get("snoozed_until")),
            context=row.get("context"),
        )

    # ------------------------------------------------------------------
    def _parse_dt(self, value: object) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=self.tz)
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=self.tz)
        raise TypeError(f"Unsupported datetime value: {value!r}")


__all__ = [
    "ActionableCandidate",
    "RuleContext",
    "RuleCallable",
    "ActionableService",
]
