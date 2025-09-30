from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine

from portfolio_tool.config import get_db_url
from portfolio_tool.data import models


if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.engine import Engine
else:  # pragma: no cover - fallback for stubbed SQLAlchemy
    Engine = Any


def ensure_db() -> Engine:
    engine = create_engine(
        get_db_url(), connect_args={"check_same_thread": False}
    )
    models.Base.metadata.create_all(engine)
    return engine


__all__ = ["ensure_db"]
