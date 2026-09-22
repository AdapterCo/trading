from decimal import Decimal

from app.backtest.engine import BacktestEngine
from app.backtest.execution_model import BacktestExecutionModel
from app.core.config import Settings
from app.exchange.types import Candle, SymbolRules
from app.strategy.types import Signal, SignalDecision


def _rules() -> SymbolRules:
    return SymbolRules(
        symbol="BTCUSDT", status="TRADING", base_asset="BTC", quote_asset="USDT",
        tick_size=Decimal("0.01"), step_size=Decimal("0.00001"),
        min_qty=Decimal("0.00001"), max_qty=Decimal("9000"),
        min_notional=Decimal("5"), max_notional=None, is_spot_trading_allowed=True,
    )


def _candle(open_time: int, close: str, *, high=None, low=None, interval="5m") -> Candle:
    c = Decimal(close)
    step = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000}[interval]
    return Candle(
        symbol="BTCUSDT", interval=interval, open_time=open_time, close_time=open_time + step - 1,
        open=c, high=Decimal(high) if high else c + Decimal("0.1"), low=Decimal(low) if low else c - Decimal("0.1"),
        close=c, volume=Decimal("10"), quote_volume=Decimal("1000"), trade_count=5,
        taker_buy_base_volume=Decimal("5"), taker_buy_quote_volume=Decimal("600"),
    )


class SpyStrategy:
    """Records every context it receives, always HOLDs — used to verify no look-ahead."""

    name = "Spy"
    version = "1.0.0"

    def __init__(self):
        self.calls = []

    def on_candle(self, candle_open_time, context):
        self.calls.append((candle_open_time, context))
        return Signal(
            symbol="BTCUSDT", strategy=self.name, strategy_version=self.version,
            decision=SignalDecision.HOLD, reference_price=0.0, candle_open_time=candle_open_time,
            reasons=[], indicator_snapshot={},
        )


class AlwaysBuyStrategy:
    """Always signals BUY — safe because the engine only asks for entries when it
    has no open position, so this can't cause more than one trade to open at once."""

    name = "FixedTest"
    version = "1.0.0"

    def on_candle(self, candle_open_time, context):
        return Signal(
            symbol="BTCUSDT", strategy=self.name, strategy_version=self.version,
            decision=SignalDecision.BUY, reference_price=0.0, candle_open_time=candle_open_time,
            reasons=[], indicator_snapshot={},
        )


def test_backtest_never_shows_the_strategy_a_still_open_higher_timeframe_candle():
    candles_5m = [_candle(i * 300_000, "100", interval="5m") for i in range(10)]
    candles_15m = [_candle(0, "100", interval="15m")]  # closes at 899_999 — not yet closed for early 5m candles

    strategy = SpyStrategy()
    engine = BacktestEngine(strategy, Settings(_env_file=None), BacktestExecutionModel(
        symbol_rules=_rules(), taker_fee_rate=Decimal("0.001"), spread=Decimal("0.001"),
        slippage=Decimal("0"), quote_asset="USDT",
    ))
    engine.run(candles_1h=[], candles_15m=candles_15m, candles_5m=candles_5m, initial_equity=Decimal("1000"))

    # the 15m candle (open_time=0, close_time=899_999) must be invisible until a 5m
    # candle whose own close_time is >= 899_999 — i.e. not for the first two 5m candles.
    first_call_context = strategy.calls[0][1]
    assert first_call_context.feature_15m is None

    # by the time enough 5m candles have closed (close_time of candle index 3 = 1_199_999 >= 899_999),
    # the 15m candle must have become visible.
    later_call_context = strategy.calls[-1][1]
    assert later_call_context.feature_15m is not None


def test_backtest_feature_5m_slice_never_includes_future_candles():
    candles_5m = [_candle(i * 300_000, "100", interval="5m") for i in range(5)]
    strategy = SpyStrategy()
    engine = BacktestEngine(strategy, Settings(_env_file=None), BacktestExecutionModel(
        symbol_rules=_rules(), taker_fee_rate=Decimal("0.001"), spread=Decimal("0"),
        slippage=Decimal("0"), quote_asset="USDT",
    ))
    engine.run(candles_1h=[], candles_15m=[], candles_5m=candles_5m, initial_equity=Decimal("1000"))

    for i, (_, context) in enumerate(strategy.calls):
        assert len(context.features_5m) == i + 1
        assert context.features_5m[-1].open_time == candles_5m[i].open_time


def test_backtest_opens_and_closes_trade_realizing_pnl_net_of_fees():
    # candle 0: BUY at close=100 with a wide-ish range to produce nonzero ATR over warmup
    candles_5m = [_candle(i * 300_000, "100", high="100.5", low="99.5") for i in range(20)]
    # a later candle spikes high enough to hit take profit (very large jump to guarantee TP)
    candles_5m.append(_candle(20 * 300_000, "100", high="200", low="99.5"))

    strategy = AlwaysBuyStrategy()
    execution_model = BacktestExecutionModel(
        symbol_rules=_rules(), taker_fee_rate=Decimal("0.001"), spread=Decimal("0"),
        slippage=Decimal("0"), quote_asset="USDT",
    )
    engine = BacktestEngine(strategy, Settings(_env_file=None), execution_model)
    result = engine.run(candles_1h=[], candles_15m=[], candles_5m=candles_5m, initial_equity=Decimal("1000"))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.realized_pnl > 0
    assert trade.fees > 0
    assert result.final_equity == Decimal("1000") + trade.realized_pnl
