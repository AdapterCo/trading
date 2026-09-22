"""BacktestEngine (instrucao.md #97, #99).

Uses the exact same Strategy class as production — never a different rule set for
history. No look-ahead: at candle N, only 1h/15m candles that have already CLOSED
by N's close_time are visible, and the 5m feature series is sliced to [0..N].

Reuses the real position-sizing math from app/risk/sizing.py (same formulas the
live RiskEngine uses) so backtest sizing isn't a second, possibly-diverging
implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.backtest.execution_model import BacktestExecutionModel
from app.core.config import Settings
from app.exchange.types import Candle
from app.features.engine import FeatureEngine
from app.risk.sizing import compute_quantity, compute_stop_price, compute_take_profit
from app.strategy.types import SignalDecision, Strategy, StrategyContext


@dataclass(frozen=True)
class BacktestTrade:
    entry_time: int
    exit_time: int
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    fees: Decimal
    realized_pnl: Decimal
    exit_reason: str


@dataclass
class _OpenPosition:
    entry_time: int
    entry_price: Decimal
    quantity: Decimal
    initial_stop: Decimal
    stop: Decimal
    take_profit: Decimal
    highest: Decimal
    entry_fee: Decimal
    break_even_active: bool = False


@dataclass(frozen=True)
class BacktestResult:
    trades: list[BacktestTrade]
    equity_curve: list[Decimal] = field(repr=False)
    final_equity: Decimal


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        settings: Settings,
        execution_model: BacktestExecutionModel,
    ) -> None:
        self._strategy = strategy
        self._settings = settings
        self._execution_model = execution_model
        self._feature_engine = FeatureEngine()

    def run(
        self,
        *,
        candles_1h: list[Candle],
        candles_15m: list[Candle],
        candles_5m: list[Candle],
        initial_equity: Decimal,
    ) -> BacktestResult:
        s = self._settings
        f1h_series = self._feature_engine.compute_series(candles_1h)
        f15m_series = self._feature_engine.compute_series(candles_15m)
        f5m_series = self._feature_engine.compute_series(candles_5m)

        equity = initial_equity
        equity_curve: list[Decimal] = []
        trades: list[BacktestTrade] = []
        position: _OpenPosition | None = None
        candles_since_last_close: int | None = None

        idx_1h = 0
        idx_15m = 0

        for i, candle in enumerate(candles_5m):
            while idx_1h + 1 < len(candles_1h) and candles_1h[idx_1h + 1].close_time <= candle.close_time:
                idx_1h += 1
            while idx_15m + 1 < len(candles_15m) and candles_15m[idx_15m + 1].close_time <= candle.close_time:
                idx_15m += 1

            f1h = f1h_series[idx_1h] if candles_1h and candles_1h[idx_1h].close_time <= candle.close_time else None
            f15m = f15m_series[idx_15m] if candles_15m and candles_15m[idx_15m].close_time <= candle.close_time else None
            f5m_slice = f5m_series[: i + 1]  # instrucao.md #99 — nothing beyond candle i is visible

            if position is not None:
                position, closed_trade = self._manage_position(candle, position, f5m_slice, f1h, f15m)
                if closed_trade is not None:
                    trades.append(closed_trade)
                    equity += closed_trade.realized_pnl
                    candles_since_last_close = 0
            else:
                if candles_since_last_close is not None:
                    candles_since_last_close += 1
                position = self._maybe_open_position(candle, f5m_slice, f1h, f15m, equity, candles_since_last_close)

            equity_curve.append(equity if position is None else equity)

        return BacktestResult(trades=trades, equity_curve=equity_curve, final_equity=equity)

    def _manage_position(self, candle, position: _OpenPosition, f5m_slice, f1h, f15m):
        s = self._settings
        current = f5m_slice[-1]

        # instrucao.md #34 priority, checked against the candle's actual range —
        # a realistic backtest can't just look at the close.
        if candle.low <= position.stop:
            return self._close_position(position, exit_price=position.stop, exit_time=candle.close_time, reason="STOP")
        if candle.high >= position.take_profit:
            return self._close_position(position, exit_price=position.take_profit, exit_time=candle.close_time, reason="TAKE_PROFIT")

        context = StrategyContext(
            feature_1h=f1h, feature_15m=f15m, features_5m=f5m_slice,
            adx_min=s.adx_min, rsi_entry_min=s.rsi_entry_min, rsi_entry_max=s.rsi_entry_max,
            pullback_max_distance=s.pullback_max_distance, min_volume_ratio=s.min_volume_ratio,
            min_taker_buy_ratio=s.min_taker_buy_ratio,
        )
        signal = self._strategy.on_candle(candle.open_time, context)

        atr = Decimal(str(current.atr14)) if current.atr14 is not None else Decimal("0")
        position.highest = max(position.highest, candle.high)
        r = position.entry_price - position.initial_stop

        if r > 0:
            if not position.break_even_active and candle.close >= position.entry_price + Decimal(str(s.break_even_trigger_r)) * r:
                position.break_even_active = True
                fees_per_unit = position.entry_fee / position.quantity if position.quantity else Decimal("0")
                position.stop = max(position.stop, position.entry_price + fees_per_unit)

            if candle.close >= position.entry_price + Decimal(str(s.trailing_start_r)) * r:
                trailing_candidate = position.highest - atr * Decimal(str(s.trailing_atr_multiplier))
                position.stop = max(position.stop, trailing_candidate)

        if signal.decision == SignalDecision.EXIT:
            return self._close_position(position, exit_price=candle.close, exit_time=candle.close_time, reason="STRATEGY_EXIT")

        return position, None

    def _close_position(self, position: _OpenPosition, *, exit_price: Decimal, exit_time: int, reason: str):
        fill = self._execution_model.market_order(side="SELL", reference_price=exit_price, requested_qty=position.quantity)
        if fill is None:
            # Can't clear exchange minimums to exit — hold instead of fabricating a close (#116).
            return position, None

        realized_pnl = (fill.price - position.entry_price) * fill.quantity - position.entry_fee - fill.fee
        trade = BacktestTrade(
            entry_time=position.entry_time, exit_time=exit_time,
            entry_price=position.entry_price, exit_price=fill.price, quantity=fill.quantity,
            fees=position.entry_fee + fill.fee, realized_pnl=realized_pnl, exit_reason=reason,
        )
        return None, trade

    def _maybe_open_position(self, candle, f5m_slice, f1h, f15m, equity: Decimal, candles_since_last_close):
        s = self._settings
        if candles_since_last_close is not None and candles_since_last_close < s.cooldown_candles:
            return None

        context = StrategyContext(
            feature_1h=f1h, feature_15m=f15m, features_5m=f5m_slice,
            adx_min=s.adx_min, rsi_entry_min=s.rsi_entry_min, rsi_entry_max=s.rsi_entry_max,
            pullback_max_distance=s.pullback_max_distance, min_volume_ratio=s.min_volume_ratio,
            min_taker_buy_ratio=s.min_taker_buy_ratio,
        )
        signal = self._strategy.on_candle(candle.open_time, context)
        if signal.decision != SignalDecision.BUY:
            return None

        current = f5m_slice[-1]
        if current.atr14 is None:
            return None
        atr = Decimal(str(current.atr14))

        stop_price = compute_stop_price(
            candle.close, atr,
            stop_atr_multiplier=Decimal(str(s.stop_atr_multiplier)), max_stop_percent=Decimal(str(s.max_stop_percent)),
        )
        if stop_price is None:
            return None

        risk_amount = equity * Decimal(str(s.risk_per_trade))
        quantity, reasons = compute_quantity(
            risk_amount=risk_amount, entry_price=candle.close, stop_price=stop_price,
            available_balance=equity * Decimal(str(s.max_capital_allocation)),
            max_capital_allocation=Decimal(str(s.max_capital_allocation)),
            symbol_rules=self._execution_model.rules,  # same filters the execution model enforces
        )
        if quantity is None:
            return None

        fill = self._execution_model.market_order(side="BUY", reference_price=candle.close, requested_qty=quantity)
        if fill is None:
            return None

        take_profit = compute_take_profit(candle.close, stop_price, take_profit_r=Decimal(str(s.take_profit_r)))

        return _OpenPosition(
            entry_time=candle.close_time, entry_price=fill.price, quantity=fill.quantity,
            initial_stop=stop_price, stop=stop_price, take_profit=take_profit,
            highest=fill.price, entry_fee=fill.fee,
        )
