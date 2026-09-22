import dataclasses

import pytest

from app.features.engine import FeatureSnapshot
from app.strategy.trend_pullback_v1 import TrendPullbackV1
from app.strategy.types import SignalDecision, StrategyContext

STRATEGY = TrendPullbackV1()

THRESHOLDS = dict(
    adx_min=20,
    rsi_entry_min=45,
    rsi_entry_max=65,
    pullback_max_distance=0.003,
    min_volume_ratio=1.0,
    min_taker_buy_ratio=0.50,
)


def _snapshot(**overrides) -> FeatureSnapshot:
    base = dict(
        symbol="BTCUSDT", interval="5m", open_time=0, close=100.0,
        ema20=None, ema50=None, ema200=None,
        rsi14=None, atr14=None, adx14=None,
        distance_ema20=None, distance_ema50=None, distance_ema200=None,
        return_1=None, return_3=None, return_12=None,
        volume_ratio=None, taker_buy_ratio=None,
    )
    base.update(overrides)
    return FeatureSnapshot(**base)


def _passing_context(**buy_overrides) -> StrategyContext:
    f1h = _snapshot(interval="1h", open_time=100, close=110.0, ema50=105.0, ema200=100.0)
    f15m = _snapshot(interval="15m", open_time=200, close=108.0, ema20=107.0, ema50=105.0, adx14=25.0)
    previous = _snapshot(interval="5m", open_time=299_700_000, close=100.0, ema20=100.05)
    current = _snapshot(
        interval="5m", open_time=300_000_000, close=100.2, ema20=100.15, ema50=99.0,
        rsi14=55.0, distance_ema20=0.0005, volume_ratio=1.2, taker_buy_ratio=0.6,
    )
    current = dataclasses.replace(current, **buy_overrides) if buy_overrides else current
    return StrategyContext(feature_1h=f1h, feature_15m=f15m, features_5m=[previous, current], **THRESHOLDS)


def test_all_conditions_pass_yields_buy():
    context = _passing_context()
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.BUY
    assert signal.reasons == []


def test_macro_filter_blocks_when_close_below_ema200():
    context = _passing_context()
    context = dataclasses.replace(
        context, feature_1h=dataclasses.replace(context.feature_1h, close=90.0)
    )
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "MACRO_CLOSE_BELOW_EMA200" in signal.reasons


def test_trend_15m_blocks_when_ema20_below_ema50():
    context = _passing_context()
    context = dataclasses.replace(
        context, feature_15m=dataclasses.replace(context.feature_15m, ema20=104.0)
    )
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "TREND_15M_EMA20_BELOW_EMA50" in signal.reasons


def test_adx_below_minimum_blocks_buy():
    context = _passing_context()
    context = dataclasses.replace(
        context, feature_15m=dataclasses.replace(context.feature_15m, adx14=15.0)
    )
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "ADX_BELOW_MINIMUM" in signal.reasons


def test_pullback_too_far_blocks_buy():
    context = _passing_context(distance_ema20=0.01)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "PULLBACK_TOO_FAR_FROM_EMA20" in signal.reasons


def test_rsi_out_of_range_blocks_buy():
    context = _passing_context(rsi14=80.0)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "RSI_OUT_OF_RANGE" in signal.reasons


def test_no_confirmation_when_close_not_higher_than_previous():
    context = _passing_context(close=99.9)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "NO_CONFIRMATION_CLOSE_NOT_HIGHER" in signal.reasons


def test_volume_not_confirmed_blocks_buy():
    context = _passing_context(volume_ratio=0.5)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "VOLUME_NOT_CONFIRMED" in signal.reasons


def test_taker_buy_ratio_unavailable_is_no_trade_not_invented():
    context = _passing_context(taker_buy_ratio=None)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "TAKER_BUY_RATIO_UNAVAILABLE" in signal.reasons


def test_taker_buy_ratio_low_blocks_buy():
    context = _passing_context(taker_buy_ratio=0.3)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "TAKER_BUY_RATIO_LOW" in signal.reasons


def test_strategic_exit_overrides_everything_else():
    context = _passing_context(close=90.0, ema20=91.0, ema50=100.0)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.EXIT
    assert signal.reasons == ["STRATEGY_EXIT_TREND_BROKEN_5M"]


def test_missing_macro_indicators_holds_not_buys():
    context = _passing_context()
    context = dataclasses.replace(context, feature_1h=None)
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.decision == SignalDecision.HOLD
    assert "MACRO_INDICATORS_NOT_READY" in signal.reasons


def test_signal_records_indicator_snapshot_and_reference_price():
    context = _passing_context()
    signal = STRATEGY.on_candle(300_000_000, context)
    assert signal.reference_price == pytest.approx(100.2)
    assert signal.indicator_snapshot["rsi14"] == pytest.approx(55.0)
    assert signal.strategy == "TrendPullbackV1"
    assert signal.candle_open_time == 300_000_000
