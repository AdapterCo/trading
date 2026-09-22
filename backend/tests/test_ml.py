from decimal import Decimal

import pytest

from app.exchange.types import Candle
from app.ml.dataset import build_dataset, classify_target, estimate_round_trip_cost
from app.ml.provider import MLSignalProvider, ModelNotVersionedError


def _candle(open_time: int, close: str) -> Candle:
    c = Decimal(close)
    return Candle(
        symbol="BTCUSDT", interval="5m", open_time=open_time, close_time=open_time + 299_999,
        open=c, high=c + Decimal("0.1"), low=c - Decimal("0.1"), close=c,
        volume=Decimal("10"), quote_volume=Decimal("1000"), trade_count=5,
        taker_buy_base_volume=Decimal("5"), taker_buy_quote_volume=Decimal("600"),
    )


def test_build_dataset_target_none_when_not_enough_future_data():
    candles = [_candle(i * 300_000, "100") for i in range(5)]
    rows = build_dataset(candles, target_horizons={"return_3": 3})
    assert rows[-1]["target_return_3"] is None
    assert rows[-1]["target_return_3"] is None


def test_build_dataset_target_computed_when_future_available():
    closes = ["100", "101", "102", "103", "104", "110"]
    candles = [_candle(i * 300_000, c) for i, c in enumerate(closes)]
    rows = build_dataset(candles, target_horizons={"return_1": 1})
    assert rows[0]["target_return_1"] == pytest.approx(0.01)  # (101-100)/100


def test_classify_target_respects_cost_threshold():
    assert classify_target(0.002, cost_threshold=0.001) == "UP"
    assert classify_target(-0.002, cost_threshold=0.001) == "DOWN"
    assert classify_target(0.0005, cost_threshold=0.001) == "NEUTRAL"
    assert classify_target(None, cost_threshold=0.001) is None


def test_estimate_round_trip_cost():
    cost = estimate_round_trip_cost(taker_fee_rate=Decimal("0.001"), spread=Decimal("0.001"), slippage=Decimal("0.0005"))
    assert cost == pytest.approx(2 * 0.001 + 0.001 + 2 * 0.0005)


def test_ml_provider_disabled_by_default_returns_none():
    provider = MLSignalProvider()
    assert provider.enabled is False
    assert provider.predict({}) is None


def test_ml_provider_enabled_without_metadata_raises():
    provider = MLSignalProvider()
    provider.enabled = True
    with pytest.raises(ModelNotVersionedError):
        provider.predict({})
