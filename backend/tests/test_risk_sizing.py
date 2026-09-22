from decimal import Decimal

from app.exchange.types import SymbolRules
from app.risk.sizing import (
    compute_quantity,
    compute_stop_price,
    compute_take_profit,
    round_down_to_step,
)


def _rules(**overrides) -> SymbolRules:
    base = dict(
        symbol="BTCUSDT", status="TRADING", base_asset="BTC", quote_asset="USDT",
        tick_size=Decimal("0.01"), step_size=Decimal("0.00001"),
        min_qty=Decimal("0.00001"), max_qty=Decimal("9000"),
        min_notional=Decimal("5"), max_notional=None, is_spot_trading_allowed=True,
    )
    base.update(overrides)
    return SymbolRules(**base)


def test_round_down_to_step_truncates():
    assert round_down_to_step(Decimal("1.23456"), Decimal("0.001")) == Decimal("1.234")


def test_round_down_to_step_zero_step_is_noop():
    assert round_down_to_step(Decimal("1.23456"), Decimal("0")) == Decimal("1.23456")


def test_compute_stop_price_within_limit():
    stop = compute_stop_price(
        Decimal("100"), Decimal("1"), stop_atr_multiplier=Decimal("1.5"), max_stop_percent=Decimal("0.02")
    )
    assert stop == Decimal("98.5")  # 1.5% distance, within 2% limit


def test_compute_stop_price_none_when_exceeds_max_percent():
    stop = compute_stop_price(
        Decimal("100"), Decimal("5"), stop_atr_multiplier=Decimal("1.5"), max_stop_percent=Decimal("0.02")
    )
    assert stop is None  # 7.5% distance > 2% limit — NO TRADE, never tightened artificially


def test_compute_take_profit_uses_r_multiple():
    take_profit = compute_take_profit(Decimal("100"), Decimal("98"), take_profit_r=Decimal("2.0"))
    assert take_profit == Decimal("104")  # R=2, entry + 2*2


def test_compute_quantity_uses_risk_amount_when_smallest():
    quantity, reasons = compute_quantity(
        risk_amount=Decimal("10"),
        entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        available_balance=Decimal("10000"),
        max_capital_allocation=Decimal("0.95"),
        symbol_rules=_rules(),
    )
    assert reasons == []
    assert quantity == Decimal("5")  # 10 / (100-98) = 5, well within balance/allocation


def test_compute_quantity_limited_by_available_balance():
    quantity, reasons = compute_quantity(
        risk_amount=Decimal("10000"),  # would demand huge quantity by risk alone
        entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        available_balance=Decimal("50"),
        max_capital_allocation=Decimal("0.95"),
        symbol_rules=_rules(),
    )
    assert reasons == []
    # balance-limited: 50/100 = 0.5, allocation-limited: (50*0.95)/100=0.475 -> smallest wins
    assert quantity == Decimal("0.475")


def test_compute_quantity_rejected_below_min_qty():
    quantity, reasons = compute_quantity(
        risk_amount=Decimal("0.0001"),
        entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        available_balance=Decimal("10000"),
        max_capital_allocation=Decimal("0.95"),
        symbol_rules=_rules(min_qty=Decimal("0.001")),
    )
    assert quantity is None
    assert "QUANTITY_BELOW_MIN_QTY" in reasons


def test_compute_quantity_rejected_below_min_notional():
    quantity, reasons = compute_quantity(
        risk_amount=Decimal("0.02"),
        entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        available_balance=Decimal("10000"),
        max_capital_allocation=Decimal("0.95"),
        symbol_rules=_rules(min_notional=Decimal("5"), min_qty=Decimal("0.00001")),
    )
    # risk-limited quantity = 0.02/2 = 0.01 -> notional = 1.0 < min_notional 5
    assert quantity is None
    assert "NOTIONAL_BELOW_MIN_NOTIONAL" in reasons


def test_compute_quantity_invalid_when_stop_not_below_entry():
    quantity, reasons = compute_quantity(
        risk_amount=Decimal("10"),
        entry_price=Decimal("100"),
        stop_price=Decimal("100"),  # zero risk per unit
        available_balance=Decimal("10000"),
        max_capital_allocation=Decimal("0.95"),
        symbol_rules=_rules(),
    )
    assert quantity is None
    assert reasons == ["INVALID_RISK_PER_UNIT"]
