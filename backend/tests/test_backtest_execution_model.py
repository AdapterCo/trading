from decimal import Decimal

from app.backtest.execution_model import BacktestExecutionModel
from app.exchange.types import SymbolRules


def _rules(**overrides) -> SymbolRules:
    base = dict(
        symbol="BTCUSDT", status="TRADING", base_asset="BTC", quote_asset="USDT",
        tick_size=Decimal("0.01"), step_size=Decimal("0.00001"),
        min_qty=Decimal("0.00001"), max_qty=Decimal("9000"),
        min_notional=Decimal("5"), max_notional=None, is_spot_trading_allowed=True,
    )
    base.update(overrides)
    return SymbolRules(**base)


def _model(**overrides):
    base = dict(
        symbol_rules=_rules(), taker_fee_rate=Decimal("0.001"),
        spread=Decimal("0.001"), slippage=Decimal("0.0005"), quote_asset="USDT",
    )
    base.update(overrides)
    return BacktestExecutionModel(**base)


def test_buy_pays_more_than_reference_price():
    model = _model()
    fill = model.market_order(side="BUY", reference_price=Decimal("100"), requested_qty=Decimal("1"))
    assert fill.price > Decimal("100")


def test_sell_receives_less_than_reference_price():
    model = _model()
    fill = model.market_order(side="SELL", reference_price=Decimal("100"), requested_qty=Decimal("1"))
    assert fill.price < Decimal("100")


def test_fee_is_taker_rate_times_notional():
    model = _model(taker_fee_rate=Decimal("0.001"), spread=Decimal("0"), slippage=Decimal("0"))
    fill = model.market_order(side="BUY", reference_price=Decimal("100"), requested_qty=Decimal("1"))
    assert fill.fee == Decimal("0.1")  # 100*1*0.001


def test_returns_none_when_below_min_notional():
    model = _model()
    fill = model.market_order(side="BUY", reference_price=Decimal("100"), requested_qty=Decimal("0.001"))
    assert fill is None  # notional ~0.1 << min_notional 5


def test_quantity_rounded_down_to_step_size():
    model = _model()
    fill = model.market_order(side="BUY", reference_price=Decimal("100"), requested_qty=Decimal("0.123456"))
    assert fill.quantity == Decimal("0.12345")
