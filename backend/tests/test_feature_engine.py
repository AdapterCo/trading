from decimal import Decimal

import pytest

from app.exchange.types import BestBidAsk, Candle
from app.features.engine import FeatureEngine
from app.features.spread import compute_spread


def _candle(open_time: int, close: float, *, taker_buy_quote=None, quote_volume=Decimal("1000")) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        interval="5m",
        open_time=open_time,
        close_time=open_time + 299_999,
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=Decimal("10"),
        quote_volume=quote_volume,
        trade_count=5,
        taker_buy_base_volume=Decimal("5"),
        taker_buy_quote_volume=taker_buy_quote if taker_buy_quote is not None else Decimal("600"),
    )


def test_compute_series_empty_input():
    assert FeatureEngine().compute_series([]) == []


def test_returns_none_before_warmup_for_long_period_indicators():
    candles = [_candle(i * 300_000, 100 + i) for i in range(5)]
    snapshot = FeatureEngine().compute_latest(candles)
    assert snapshot.ema200 is None  # not enough candles yet
    assert snapshot.rsi14 is None
    assert snapshot.return_1 is not None  # only needs 1 prior candle


def test_return_1_matches_simple_percentage_change():
    candles = [_candle(0, 100), _candle(300_000, 110)]
    snapshot = FeatureEngine().compute_latest(candles)
    assert snapshot.return_1 == pytest.approx(0.10)


def test_taker_buy_ratio_is_none_when_quote_volume_zero():
    candles = [_candle(0, 100, quote_volume=Decimal("0"))]
    snapshot = FeatureEngine().compute_latest(candles)
    assert snapshot.taker_buy_ratio is None


def test_taker_buy_ratio_computed_normally():
    candles = [_candle(0, 100, taker_buy_quote=Decimal("600"), quote_volume=Decimal("1000"))]
    snapshot = FeatureEngine().compute_latest(candles)
    assert snapshot.taker_buy_ratio == pytest.approx(0.6)


def test_volume_ratio_none_before_sma_warmup():
    candles = [_candle(i * 300_000, 100) for i in range(5)]
    snapshot = FeatureEngine().compute_latest(candles)
    assert snapshot.volume_ratio is None  # needs 20 candles for Volume SMA20


def test_distance_ema_is_zero_when_flat_market():
    candles = [_candle(i * 300_000, 100) for i in range(25)]
    snapshot = FeatureEngine().compute_latest(candles)
    assert snapshot.distance_ema20 == pytest.approx(0.0, abs=1e-9)


def test_compute_spread_basic():
    quote = BestBidAsk(
        symbol="BTCUSDT",
        bid_price=Decimal("100"),
        bid_qty=Decimal("1"),
        ask_price=Decimal("100.1"),
        ask_qty=Decimal("1"),
    )
    spread = compute_spread(quote)
    expected = Decimal("0.1") / Decimal("100.05")
    assert float(spread) == pytest.approx(float(expected), abs=1e-9)
