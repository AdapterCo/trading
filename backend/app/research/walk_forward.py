"""WalkForwardEngine (instrucao.md #102). Produces analysis only — never touches
production automatically. Runs BacktestEngine repeatedly over rolling, non-overlapping
time windows so a strategy's consistency across different market regimes is visible.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.backtest.engine import BacktestEngine, BacktestResult
from app.backtest.execution_model import BacktestExecutionModel
from app.core.config import Settings
from app.exchange.types import Candle
from app.strategy.types import Strategy


@dataclass(frozen=True)
class WalkForwardWindow:
    start_open_time: int
    end_close_time: int
    result: BacktestResult


class WalkForwardEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        strategy_factory: Callable[[], Strategy],
        execution_model_factory: Callable[[], BacktestExecutionModel],
    ) -> None:
        self._settings = settings
        self._strategy_factory = strategy_factory
        self._execution_model_factory = execution_model_factory

    def run(
        self,
        *,
        candles_1h: list[Candle],
        candles_15m: list[Candle],
        candles_5m: list[Candle],
        window_candles: int,
        step_candles: int,
        initial_equity: Decimal,
    ) -> list[WalkForwardWindow]:
        if window_candles <= 0 or step_candles <= 0:
            raise ValueError("window_candles and step_candles must be positive")

        windows: list[WalkForwardWindow] = []
        for start in range(0, len(candles_5m) - window_candles + 1, step_candles):
            window_5m = candles_5m[start : start + window_candles]
            window_start = window_5m[0].open_time
            window_end = window_5m[-1].close_time

            window_15m = [c for c in candles_15m if window_start <= c.open_time <= window_end]
            window_1h = [c for c in candles_1h if window_start <= c.open_time <= window_end]

            engine = BacktestEngine(self._strategy_factory(), self._settings, self._execution_model_factory())
            result = engine.run(
                candles_1h=window_1h, candles_15m=window_15m, candles_5m=window_5m, initial_equity=initial_equity
            )
            windows.append(WalkForwardWindow(start_open_time=window_start, end_close_time=window_end, result=result))

        return windows
