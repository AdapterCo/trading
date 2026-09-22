from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import MarketDataCandle  # noqa: F401 — registers table on Base.metadata
from app.exchange.types import Candle
from app.market_data.repository import CandleRepository


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _candle(open_time: int) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + 59_999,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("10"),
        quote_volume=Decimal("1000"),
        trade_count=5,
        taker_buy_base_volume=Decimal("5"),
        taker_buy_quote_volume=Decimal("500"),
    )


def test_upsert_many_is_idempotent(session):
    repo = CandleRepository(session)
    candles = [_candle(0), _candle(60_000)]

    repo.upsert_many(candles, source="test")
    repo.upsert_many(candles, source="test")  # re-run, must not duplicate rows

    assert repo.count("BTCUSDT", "1m") == 2


def test_latest_open_time(session):
    repo = CandleRepository(session)
    repo.upsert_many([_candle(0), _candle(60_000), _candle(120_000)], source="test")
    assert repo.latest_open_time("BTCUSDT", "1m") == 120_000


def test_latest_open_time_none_when_empty(session):
    repo = CandleRepository(session)
    assert repo.latest_open_time("BTCUSDT", "1m") is None


def test_get_recent_returns_ascending_order(session):
    repo = CandleRepository(session)
    repo.upsert_many([_candle(0), _candle(60_000), _candle(120_000)], source="test")
    recent = repo.get_recent("BTCUSDT", "1m", limit=2)
    assert [c.open_time for c in recent] == [60_000, 120_000]
