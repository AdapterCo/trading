"""Strategy interface and Signal (instrucao.md #13, #25).

StrategyEngine never sends orders and never imports an exchange SDK — it only
looks at features already computed by FeatureEngine and returns a Signal.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.features.engine import FeatureSnapshot


class SignalDecision(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    EXIT = "EXIT"


@dataclass(frozen=True)
class Signal:
    symbol: str
    strategy: str
    strategy_version: str
    decision: SignalDecision
    reference_price: float
    candle_open_time: int
    reasons: list[str]
    indicator_snapshot: dict

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class StrategyContext:
    """Everything a Strategy needs besides the triggering candle (instrucao.md #15, #16)."""

    feature_1h: FeatureSnapshot | None
    feature_15m: FeatureSnapshot | None
    features_5m: list[FeatureSnapshot]  # ascending order; features_5m[-1] is the current candle

    adx_min: float
    rsi_entry_min: float
    rsi_entry_max: float
    pullback_max_distance: float
    min_volume_ratio: float
    min_taker_buy_ratio: float


class Strategy:
    name: str
    version: str

    def on_candle(self, candle_open_time: int, context: StrategyContext) -> Signal:
        raise NotImplementedError
