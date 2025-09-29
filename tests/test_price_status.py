from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from portfolio_tool.config import Config
from portfolio_tool.data import models
from ui.textual_app import PortfolioServices, PriceStatus


@pytest.fixture
def mem_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    return Session


class MemoryDatabase:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @contextmanager
    def session_scope(self):
        session = self._session_factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()


class DummyPricing:
    def get_quotes(self, session, symbols):  # pragma: no cover - protocol stub
        return {}


def make_services(mem_session_factory):
    cfg = Config()
    db = MemoryDatabase(mem_session_factory)
    pricing = DummyPricing()
    return PortfolioServices(cfg=cfg, db=db, pricing=pricing)


def test_select_limit_compatibility():
    stmt = select(models.PriceCache)
    try:
        _ = stmt.limit(1)
    except AttributeError:  # pragma: no cover - explicit failure path
        pytest.fail(
            "Your SQLAlchemy 'select' does not support .limit(...). "
            "Check that you're importing 'select' from 'sqlalchemy' and using SQLAlchemy>=1.4."
        )


def test_get_price_status_no_rows(mem_session):
    services = make_services(mem_session)

    status = services.get_price_status()

    assert isinstance(status, PriceStatus)
    assert status.asof is None
    assert status.stale is True


def test_get_price_status_with_row(mem_session):
    session = mem_session()
    now = datetime.now(timezone.utc)
    price_cache = models.PriceCache(
        symbol="CSL.AX",
        price=123.45,
        currency="AUD",
        asof=now,
        provider="yfinance",
        ttl_expires_at=now + timedelta(minutes=15),
        is_stale=False,
    )
    session.add(price_cache)
    session.commit()
    session.close()

    services = make_services(mem_session)

    status = services.get_price_status()

    assert status.asof == now
    assert status.stale is False
