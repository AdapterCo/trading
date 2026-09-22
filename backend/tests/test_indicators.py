"""Indicator math tests (instrucao.md #14, #95). Values verified by hand against
the standard SMA/EMA/Wilder-RSI/Wilder-ATR/Wilder-ADX formulas.
"""
from __future__ import annotations

import pytest

from app.indicators.core import adx, atr, ema, rsi, sma


def test_sma_basic():
    values = [1, 2, 3, 4, 5]
    result = sma(values, period=3)
    assert result == [None, None, 2.0, 3.0, 4.0]


def test_ema_seeded_with_sma_then_recursive():
    # period=3, multiplier=0.5; seed = mean(1,2,3)=2.0
    values = [1, 2, 3, 4, 5]
    result = ema(values, period=3)
    assert result[0] is None and result[1] is None
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx((4 - 2.0) * 0.5 + 2.0)  # 3.0
    assert result[4] == pytest.approx((5 - 3.0) * 0.5 + 3.0)  # 4.0


def test_rsi_hand_verified_period_3():
    closes = [1, 2, 3, 4, 3, 2, 1, 2, 3, 4]
    result = rsi(closes, period=3)

    assert result[0] is None
    assert result[3] == pytest.approx(100.0, abs=0.01)
    assert result[4] == pytest.approx(66.6667, abs=0.01)
    assert result[5] == pytest.approx(44.4444, abs=0.01)
    assert result[6] == pytest.approx(29.6296, abs=0.01)
    assert result[7] == pytest.approx(53.0863, abs=0.01)
    assert result[8] == pytest.approx(68.7243, abs=0.01)
    assert result[9] == pytest.approx(79.1497, abs=0.01)


def test_rsi_bounded_between_0_and_100():
    closes = [100.0, 105, 98, 110, 90, 120, 80, 130, 70, 140, 60, 150, 50, 160, 40]
    result = rsi(closes, period=14)
    values = [v for v in result if v is not None]
    assert values
    for v in values:
        assert 0.0 <= v <= 100.0


def test_atr_hand_verified_period_3():
    highs = [10, 12, 11, 13, 14, 13, 15]
    lows = [8, 9, 9, 10, 11, 11, 12]
    closes = [9, 11, 10, 12, 13, 12, 14]

    result = atr(highs, lows, closes, period=3)

    assert result[0] is None and result[1] is None
    assert result[2] == pytest.approx(2.3333, abs=0.001)
    assert result[3] == pytest.approx(2.5556, abs=0.001)
    assert result[4] == pytest.approx(2.7037, abs=0.001)
    assert result[5] == pytest.approx(2.4691, abs=0.001)
    assert result[6] == pytest.approx(2.6461, abs=0.001)


def test_adx_strong_uptrend_is_high_and_bounded():
    n = 40
    highs = [100.0 + i * 2 for i in range(n)]
    lows = [98.0 + i * 2 for i in range(n)]
    closes = [99.0 + i * 2 for i in range(n)]

    result = adx(highs, lows, closes, period=14)
    values = [v for v in result if v is not None]

    assert values, "ADX should produce values once enough candles are available"
    for v in values:
        assert 0.0 <= v <= 100.0
    # A clean, strong, monotonic trend should push ADX well above the ADX_MIN=20 threshold (#17).
    assert values[-1] > 20.0


def test_adx_flat_market_stays_low():
    n = 40
    highs = [100.0] * n
    lows = [99.0] * n
    closes = [99.5] * n

    result = adx(highs, lows, closes, period=14)
    values = [v for v in result if v is not None]

    assert values
    for v in values:
        assert v == pytest.approx(0.0, abs=0.01)
