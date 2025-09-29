from __future__ import annotations

from __future__ import annotations

from pathlib import Path

import pytest

from portfolio_tool.config import Config
from portfolio_tool.data.repo import Database


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    config = Config()
    config.db_path = tmp_path / "portfolio.db"
    return config


@pytest.fixture
def db(cfg: Config) -> Database:
    database = Database(cfg)
    database.create_all()
    return database


@pytest.fixture
def session(db: Database):
    with db.session_scope() as session:
        yield session
