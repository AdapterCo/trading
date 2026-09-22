"""TrendPullbackV1 (instrucao.md #13-#25, #33).

Trend Following + Pullback, Long Only. Every rule from #24's BUY checklist is
evaluated; any failure appends a reason and forces HOLD. Missing/None indicator
values (warmup incomplete, division-by-zero guarded by FeatureEngine) are never
treated as passing — instrucao.md #116: UNKNOWN -> block, never assume.
"""
from __future__ import annotations

from dataclasses import asdict

from app.strategy.types import Signal, SignalDecision, Strategy, StrategyContext


class TrendPullbackV1(Strategy):
    name = "TrendPullbackV1"
    version = "1.0.0"

    def on_candle(self, candle_open_time: int, context: StrategyContext) -> Signal:
        current = context.features_5m[-1] if context.features_5m else None
        if current is None or current.open_time != candle_open_time:
            return self._hold(candle_open_time, current, ["MISSING_5M_FEATURE_FOR_CANDLE"])

        if self._strategic_exit(context):
            return self._signal(
                candle_open_time, current, SignalDecision.EXIT, ["STRATEGY_EXIT_TREND_BROKEN_5M"]
            )

        reasons = self._buy_rejection_reasons(context)
        decision = SignalDecision.BUY if not reasons else SignalDecision.HOLD
        return self._signal(candle_open_time, current, decision, reasons)

    def _strategic_exit(self, context: StrategyContext) -> bool:
        """instrucao.md #33 — close < EMA50_5m AND EMA20_5m < EMA50_5m on closed candle."""
        current = context.features_5m[-1]
        if current.ema20 is None or current.ema50 is None:
            return False
        return current.close < current.ema50 and current.ema20 < current.ema50

    def _buy_rejection_reasons(self, context: StrategyContext) -> list[str]:
        reasons: list[str] = []
        f1h = context.feature_1h
        f15m = context.feature_15m
        current = context.features_5m[-1]
        previous = context.features_5m[-2] if len(context.features_5m) >= 2 else None

        # --- 1H macro filter (instrucao.md #15) ---
        if f1h is None or f1h.ema200 is None or f1h.ema50 is None:
            reasons.append("MACRO_INDICATORS_NOT_READY")
        else:
            if not (f1h.close > f1h.ema200):
                reasons.append("MACRO_CLOSE_BELOW_EMA200")
            if not (f1h.ema50 > f1h.ema200):
                reasons.append("MACRO_EMA50_BELOW_EMA200")

        # --- 15M trend (instrucao.md #16) ---
        if f15m is None or f15m.ema20 is None or f15m.ema50 is None:
            reasons.append("TREND_15M_INDICATORS_NOT_READY")
        else:
            if not (f15m.ema20 > f15m.ema50):
                reasons.append("TREND_15M_EMA20_BELOW_EMA50")
            if not (f15m.close > f15m.ema50):
                reasons.append("TREND_15M_CLOSE_BELOW_EMA50")

        # --- ADX (instrucao.md #17) ---
        if f15m is None or f15m.adx14 is None:
            reasons.append("ADX_NOT_READY")
        elif f15m.adx14 < context.adx_min:
            reasons.append("ADX_BELOW_MINIMUM")

        # --- Pullback (instrucao.md #18) ---
        if current.distance_ema20 is None:
            reasons.append("PULLBACK_DISTANCE_NOT_READY")
        elif current.distance_ema20 > context.pullback_max_distance:
            reasons.append("PULLBACK_TOO_FAR_FROM_EMA20")

        # --- RSI (instrucao.md #19) ---
        if current.rsi14 is None:
            reasons.append("RSI_NOT_READY")
        elif not (context.rsi_entry_min <= current.rsi14 <= context.rsi_entry_max):
            reasons.append("RSI_OUT_OF_RANGE")

        # --- Confirmation (instrucao.md #20) ---
        if previous is None:
            reasons.append("CONFIRMATION_NOT_READY")
        else:
            if not (current.close > previous.close):
                reasons.append("NO_CONFIRMATION_CLOSE_NOT_HIGHER")
            if current.ema20 is None or not (current.close > current.ema20):
                reasons.append("NO_CONFIRMATION_CLOSE_BELOW_EMA20")

        # --- Volume (instrucao.md #21) ---
        if current.volume_ratio is None:
            reasons.append("VOLUME_RATIO_NOT_READY")
        elif current.volume_ratio < context.min_volume_ratio:
            reasons.append("VOLUME_NOT_CONFIRMED")

        # --- Taker buy ratio (instrucao.md #22) — missing data means NO TRADE, never invent ---
        if current.taker_buy_ratio is None:
            reasons.append("TAKER_BUY_RATIO_UNAVAILABLE")
        elif current.taker_buy_ratio < context.min_taker_buy_ratio:
            reasons.append("TAKER_BUY_RATIO_LOW")

        return reasons

    def _hold(self, candle_open_time: int, current, reasons: list[str]) -> Signal:
        return self._signal(candle_open_time, current, SignalDecision.HOLD, reasons)

    def _signal(self, candle_open_time: int, current, decision: SignalDecision, reasons: list[str]) -> Signal:
        return Signal(
            symbol=current.symbol if current else "",
            strategy=self.name,
            strategy_version=self.version,
            decision=decision,
            reference_price=current.close if current else 0.0,
            candle_open_time=candle_open_time,
            reasons=reasons,
            indicator_snapshot=asdict(current) if current else {},
        )
