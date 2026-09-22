"""ML dataset generation (instrucao.md #73, #74).

Features at row i come from FeatureEngine.compute_series, which is causal by
construction (index i only ever sees candles[0..i]) — same guarantee the live
Strategy relies on. Targets are the only place allowed to look into the future
(instrucao.md #74): they use candles AFTER i, which is what a target must predict.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal

from app.exchange.types import Candle
from app.features.engine import FeatureEngine

# lookahead measured in number of candles at whatever interval `candles` uses.
DEFAULT_TARGET_HORIZONS = {"return_1": 1, "return_3": 3, "return_6": 6, "return_12": 12}


def build_dataset(candles: list[Candle], *, target_horizons: dict[str, int] | None = None) -> list[dict]:
    horizons = target_horizons or DEFAULT_TARGET_HORIZONS
    feature_series = FeatureEngine().compute_series(candles)

    rows: list[dict] = []
    for i, snapshot in enumerate(feature_series):
        row = asdict(snapshot)
        current_close = candles[i].close
        for name, lookahead in horizons.items():
            j = i + lookahead
            if j < len(candles) and current_close != 0:
                future_close = candles[j].close
                row[f"target_{name}"] = float((future_close - current_close) / current_close)
            else:
                # Not enough future data yet to know the outcome — never invented (#74, #116).
                row[f"target_{name}"] = None
        rows.append(row)
    return rows


def classify_target(
    return_value: float | None, *, cost_threshold: float
) -> str | None:
    """instrucao.md #73 — a target must clear real trading costs (fees+spread+slippage)
    to count as UP/DOWN; otherwise a technically-positive move that a real trade
    would lose money on gets mislabeled as an opportunity."""
    if return_value is None:
        return None
    if return_value > cost_threshold:
        return "UP"
    if return_value < -cost_threshold:
        return "DOWN"
    return "NEUTRAL"


def estimate_round_trip_cost(*, taker_fee_rate: Decimal, spread: Decimal, slippage: Decimal) -> float:
    """Two fee legs (entry+exit) plus one spread crossing plus slippage on each leg."""
    return float(2 * taker_fee_rate + spread + 2 * slippage)
