"""FeatureEngine (instrucao.md #70). Computes indicators/features from closed candles only.

Never fabricates values: when a required input is missing or a computation is
undefined (e.g. division by zero on taker_buy_ratio), the corresponding feature
is None rather than a guessed number — callers (Strategy, in Fase 5) must treat
None as NO TRADE (instrucao.md #22, #116).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.exchange.types import Candle
from app.indicators.core import adx, atr, ema, rsi, sma

EMA_PERIODS = (20, 50, 200)
RSI_PERIOD = 14
ATR_PERIOD = 14
ADX_PERIOD = 14
VOLUME_SMA_PERIOD = 20


@dataclass(frozen=True)
class FeatureSnapshot:
    symbol: str
    interval: str
    open_time: int
    close: float

    ema20: float | None
    ema50: float | None
    ema200: float | None

    rsi14: float | None
    atr14: float | None
    adx14: float | None

    distance_ema20: float | None
    distance_ema50: float | None
    distance_ema200: float | None

    return_1: float | None
    return_3: float | None
    return_12: float | None

    volume_ratio: float | None
    taker_buy_ratio: float | None


class FeatureEngine:
    def compute_series(self, candles: list[Candle]) -> list[FeatureSnapshot | None]:
        """Returns one snapshot per candle (None where indicators aren't warmed up yet).

        `candles` must be closed candles in ascending open_time order (instrucao.md #11).
        """
        if not candles:
            return []

        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        volumes = [float(c.volume) for c in candles]

        ema_series = {p: ema(closes, p) for p in EMA_PERIODS}
        rsi_series = rsi(closes, RSI_PERIOD)
        atr_series = atr(highs, lows, closes, ATR_PERIOD)
        adx_series = adx(highs, lows, closes, ADX_PERIOD)
        volume_sma_series = sma(volumes, VOLUME_SMA_PERIOD)

        out: list[FeatureSnapshot | None] = []
        for i, candle in enumerate(candles):
            e20, e50, e200 = ema_series[20][i], ema_series[50][i], ema_series[200][i]

            out.append(
                FeatureSnapshot(
                    symbol=candle.symbol,
                    interval=candle.interval,
                    open_time=candle.open_time,
                    close=closes[i],
                    ema20=e20,
                    ema50=e50,
                    ema200=e200,
                    rsi14=rsi_series[i],
                    atr14=atr_series[i],
                    adx14=adx_series[i],
                    distance_ema20=_distance(closes[i], e20),
                    distance_ema50=_distance(closes[i], e50),
                    distance_ema200=_distance(closes[i], e200),
                    return_1=_return(closes, i, 1),
                    return_3=_return(closes, i, 3),
                    return_12=_return(closes, i, 12),
                    volume_ratio=_ratio(volumes[i], volume_sma_series[i]),
                    taker_buy_ratio=_taker_buy_ratio(candle),
                )
            )
        return out

    def compute_latest(self, candles: list[Candle]) -> FeatureSnapshot | None:
        series = self.compute_series(candles)
        return series[-1] if series else None


def _distance(close: float, ema_value: float | None) -> float | None:
    if ema_value is None or ema_value == 0:
        return None
    return abs(close - ema_value) / ema_value


def _return(closes: list[float], i: int, lookback: int) -> float | None:
    if i - lookback < 0:
        return None
    prev = closes[i - lookback]
    if prev == 0:
        return None
    return (closes[i] - prev) / prev


def _ratio(value: float, baseline: float | None) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return value / baseline


def _taker_buy_ratio(candle: Candle) -> float | None:
    """instrucao.md #22 — never invent when the underlying data is missing/invalid."""
    total = candle.quote_volume
    if total is None or total == Decimal("0"):
        return None
    return float(candle.taker_buy_quote_volume / total)
