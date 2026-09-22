import time
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import MarketDataCandle  # noqa: F401
from app.exchange.types import Candle
from app.market_data.engine import MarketDataEngine
from app.market_data.repository import CandleRepository


class FakeExchange:
    """Returns a fixed number of candles once, then nothing — never fabricates more."""

    def __init__(self, available_count: int):
        self._available_count = available_count

    def get_klines(self, symbol, interval, *, start_time=None, end_time=None, limit=1000):
        candles = []
        for i in range(min(self._available_count, limit)):
            open_time = i * 60_000
            candles.append(
                Candle(
                    symbol=symbol,
                    interval=interval,
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
            )
        self._available_count = 0  # exhaust on second page request
        return candles


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ensure_warmup_ready_when_enough_candles_available():
    repo = CandleRepository(_session())
    engine = MarketDataEngine(FakeExchange(250), repo, stale_timeout_seconds=90)

    status = engine.ensure_warmup("BTCUSDT", "1m", required=200)
    assert status.ready is True
    assert status.candle_count == 250


def test_ensure_warmup_not_ready_when_exchange_has_fewer_candles():
    repo = CandleRepository(_session())
    engine = MarketDataEngine(FakeExchange(50), repo, stale_timeout_seconds=90)

    status = engine.ensure_warmup("BTCUSDT", "1m", required=200)
    assert status.ready is False
    assert status.candle_count == 50


def test_is_stale_true_before_any_heartbeat():
    repo = CandleRepository(_session())
    engine = MarketDataEngine(FakeExchange(0), repo, stale_timeout_seconds=90)
    assert engine.is_stale("BTCUSDT", "1m") is True


def test_is_stale_false_right_after_heartbeat():
    repo = CandleRepository(_session())
    engine = MarketDataEngine(FakeExchange(0), repo, stale_timeout_seconds=90)
    engine.record_stream_heartbeat("BTCUSDT", "1m")
    assert engine.is_stale("BTCUSDT", "1m") is False


def test_is_stale_true_after_timeout_elapsed(monkeypatch):
    repo = CandleRepository(_session())
    engine = MarketDataEngine(FakeExchange(0), repo, stale_timeout_seconds=1)
    engine.record_stream_heartbeat("BTCUSDT", "1m")

    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 5)
    assert engine.is_stale("BTCUSDT", "1m") is True
