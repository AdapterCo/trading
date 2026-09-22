"""Technical indicators (instrucao.md #14). Pure functions over float series.

Float is used here intentionally — instrucao.md #8 permits float for statistical
processing where accounting-level precision is not required. Raw candle data in
the database stays Decimal; only this indicator layer converts to float.

Each function returns a list aligned 1:1 with the input (None where the window
is not yet full), so the same series can be reused for both live decisions and
backtesting (instrucao.md #97 requires identical logic in both).
"""
from __future__ import annotations


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        out[i] = sum(window) / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    multiplier = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (values[i] - prev) * multiplier + prev
        out[i] = prev
    return out


def _wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Wilder's smoothing (used by RSI, ATR, ADX) — seeded with a simple average."""
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    if len(closes) < period + 1:
        return [None] * len(closes)

    gains = [0.0] * len(closes)
    losses = [0.0] * len(closes)
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains[i] = max(change, 0.0)
        losses[i] = max(-change, 0.0)

    # Smoothing operates on changes, which start at index 1 — shift the window.
    avg_gain = _wilder_smooth(gains[1:], period)
    avg_loss = _wilder_smooth(losses[1:], period)

    out: list[float | None] = [None] * len(closes)
    for i in range(len(avg_gain)):
        ag, al = avg_gain[i], avg_loss[i]
        if ag is None or al is None:
            continue
        idx = i + 1  # undo the shift applied above
        if al == 0:
            out[idx] = 100.0
        elif ag == 0:
            out[idx] = 0.0
        else:
            rs = ag / al
            out[idx] = 100 - (100 / (1 + rs))
    return out


def true_range(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    tr = [0.0] * len(highs)
    tr[0] = highs[0] - lows[0]
    for i in range(1, len(highs)):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    return tr


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    tr = true_range(highs, lows, closes)
    return _wilder_smooth(tr, period)


def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    n = len(highs)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    tr = true_range(highs, lows, closes)

    smoothed_tr = _wilder_smooth(tr, period)
    smoothed_plus_dm = _wilder_smooth(plus_dm, period)
    smoothed_minus_dm = _wilder_smooth(minus_dm, period)

    dx: list[float | None] = [None] * n
    for i in range(n):
        st, spd, smd = smoothed_tr[i], smoothed_plus_dm[i], smoothed_minus_dm[i]
        if st is None or spd is None or smd is None or st == 0:
            continue
        plus_di = 100 * spd / st
        minus_di = 100 * smd / st
        denom = plus_di + minus_di
        dx[i] = 0.0 if denom == 0 else 100 * abs(plus_di - minus_di) / denom

    dx_values = [v for v in dx if v is not None]
    first_dx_index = next((i for i, v in enumerate(dx) if v is not None), None)
    if first_dx_index is None or len(dx_values) < period:
        return [None] * n

    smoothed_dx = _wilder_smooth(dx_values, period)
    out: list[float | None] = [None] * n
    for offset, val in enumerate(smoothed_dx):
        out[first_dx_index + offset] = val
    return out
