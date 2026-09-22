from decimal import Decimal

import pytest

from app.backtest.execution_model import BacktestExecutionModel
from app.core.config import Settings
from app.exchange.types import Candle, SymbolRules
from app.research.data_split import split_chronologically
from app.research.walk_forward import WalkForwardEngine
from app.strategy.types import Signal, SignalDecision


def _rules() -> SymbolRules:
    return SymbolRules(
        symbol="BTCUSDT", status="TRADING", base_asset="BTC", quote_asset="USDT",
        tick_size=Decimal("0.01"), step_size=Decimal("0.00001"),
        min_qty=Decimal("0.00001"), max_qty=Decimal("9000"),
        min_notional=Decimal("5"), max_notional=None, is_spot_trading_allowed=True,
    )


def _candle(open_time: int) -> Candle:
    return Candle(
        symbol="BTCUSDT", interval="5m", open_time=open_time, close_time=open_time + 299_999,
        open=Decimal("100"), high=Decimal("100.1"), low=Decimal("99.9"), close=Decimal("100"),
        volume=Decimal("10"), quote_volume=Decimal("1000"), trade_count=5,
        taker_buy_base_volume=Decimal("5"), taker_buy_quote_volume=Decimal("600"),
    )


class AlwaysHoldStrategy:
    name = "Hold"
    version = "1.0.0"

    def on_candle(self, candle_open_time, context):
        return Signal(
            symbol="BTCUSDT", strategy=self.name, strategy_version=self.version,
            decision=SignalDecision.HOLD, reference_price=0.0, candle_open_time=candle_open_time,
            reasons=[], indicator_snapshot={},
        )


def test_split_chronologically_is_ordered_and_non_overlapping():
    candles = [_candle(i * 300_000) for i in range(100)]
    split = split_chronologically(candles, train_ratio=0.6, validation_ratio=0.2)

    assert len(split.train) == 60
    assert len(split.validation) == 20
    assert len(split.test) == 20
    assert split.train[-1].open_time < split.validation[0].open_time
    assert split.validation[-1].open_time < split.test[0].open_time


def test_split_chronologically_rejects_invalid_ratios():
    with pytest.raises(ValueError):
        split_chronologically([_candle(0)], train_ratio=0.7, validation_ratio=0.4)


def test_walk_forward_produces_one_window_per_step():
    candles_5m = [_candle(i * 300_000) for i in range(50)]
    engine = WalkForwardEngine(
        settings=Settings(_env_file=None),
        strategy_factory=lambda: AlwaysHoldStrategy(),
        execution_model_factory=lambda: BacktestExecutionModel(
            symbol_rules=_rules(), taker_fee_rate=Decimal("0.001"), spread=Decimal("0"),
            slippage=Decimal("0"), quote_asset="USDT",
        ),
    )
    windows = engine.run(
        candles_1h=[], candles_15m=[], candles_5m=candles_5m,
        window_candles=20, step_candles=10, initial_equity=Decimal("1000"),
    )
    assert len(windows) == 4  # starts at 0, 10, 20, 30 (30+20=50 fits exactly)
    for w in windows:
        assert w.result.final_equity == Decimal("1000")  # AlwaysHold never trades
