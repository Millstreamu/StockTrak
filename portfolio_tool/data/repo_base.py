"""Repository base abstractions for persistence backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Migration:
    """Represents a database migration script."""

    version: str
    name: str
    sql: str


class RepositoryError(RuntimeError):
    """Raised when the repository encounters an unrecoverable error."""


class BaseRepository(ABC):
    """Abstract repository API shared by all persistence backends."""

    # --- lifecycle -----------------------------------------------------
    def close(self) -> None:
        """Close any underlying resources (optional)."""

    # --- transactions --------------------------------------------------
    @abstractmethod
    def add_transaction(self, txn: Mapping[str, Any]) -> int:
        """Insert a transaction and return its identifier."""

    @abstractmethod
    def get_transaction(self, txn_id: int) -> dict[str, Any] | None:
        """Fetch a transaction by identifier."""

    @abstractmethod
    def list_transactions(
        self,
        *,
        symbol: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str = "asc",
    ) -> list[dict[str, Any]]:
        """List transactions optionally filtered by symbol."""

    @abstractmethod
    def update_transaction(self, txn_id: int, updates: Mapping[str, Any]) -> None:
        """Apply updates to an existing transaction."""

    @abstractmethod
    def delete_transaction(self, txn_id: int) -> None:
        """Remove a transaction by identifier."""

    # --- lots ----------------------------------------------------------
    @abstractmethod
    def add_lot(self, lot: Mapping[str, Any]) -> int:
        """Persist a cost base lot."""

    @abstractmethod
    def update_lot(self, lot_id: int, updates: Mapping[str, Any]) -> None:
        """Update a stored lot."""

    @abstractmethod
    def list_lots(
        self,
        *,
        symbol: str | None = None,
        only_open: bool = False,
    ) -> list[dict[str, Any]]:
        """Return lots, optionally filtered by symbol or open quantity."""

    @abstractmethod
    def delete_lot(self, lot_id: int) -> None:
        """Delete a lot (used for data resets/testing)."""

    # --- disposals -----------------------------------------------------
    @abstractmethod
    def add_disposal(self, disposal: Mapping[str, Any]) -> int:
        """Insert a disposal slice."""

    @abstractmethod
    def list_disposals(
        self,
        *,
        sell_txn_id: int | None = None,
        lot_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List disposal slices filtered by sell transaction or lot."""

    @abstractmethod
    def delete_disposals_for_sell(self, sell_txn_id: int) -> None:
        """Remove existing disposal links for a sell transaction."""

    # --- price cache ---------------------------------------------------
    @abstractmethod
    def upsert_price(self, record: Mapping[str, Any]) -> None:
        """Store or update a cached price quote."""

    @abstractmethod
    def get_prices(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        """Return cached price quotes for the requested symbols."""

    @abstractmethod
    def purge_price(self, symbol: str) -> None:
        """Remove a cached price entry."""

    # --- actionables ---------------------------------------------------
    @abstractmethod
    def add_actionable(self, actionable: Mapping[str, Any]) -> int:
        """Persist a new actionable item."""

    @abstractmethod
    def update_actionable(self, actionable_id: int, updates: Mapping[str, Any]) -> None:
        """Update fields on an actionable item."""

    @abstractmethod
    def list_actionables(
        self,
        *,
        status: str | None = None,
        include_snoozed: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieve actionable items optionally filtered by status."""

    # --- utility -------------------------------------------------------
    def __enter__(self) -> "BaseRepository":  # pragma: no cover - convenience
        return self

    def __exit__(self, *exc_info: object) -> None:  # pragma: no cover - convenience
        self.close()


def normalise_order(order: str) -> str:
    """Validate ordering inputs."""

    order = (order or "asc").lower()
    if order not in {"asc", "desc"}:
        raise RepositoryError(f"Unsupported order: {order!r}")
    return order


__all__ = [
    "BaseRepository",
    "RepositoryError",
    "Migration",
    "normalise_order",
]
