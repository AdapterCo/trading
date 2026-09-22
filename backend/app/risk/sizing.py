"""Stop/take-profit/position-size math (instrucao.md #26-#29). All Decimal — instrucao.md #8."""
from __future__ import annotations

from decimal import Decimal

from app.exchange.types import SymbolRules


def round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Never round up — instrucao.md #43 forbids arbitrary rounding of qty/price,
    and rounding a BUY quantity up could exceed the intended risk."""
    if step <= 0:
        return value
    return (value // step) * step


def compute_stop_price(
    entry_price: Decimal, atr: Decimal, *, stop_atr_multiplier: Decimal, max_stop_percent: Decimal
) -> Decimal | None:
    """instrucao.md #26. Returns None (NO TRADE) if the natural stop exceeds MAX_STOP_PERCENT.

    Never artificially tightens the stop to fit the limit — a tighter-than-ATR
    stop would misrepresent the actual risk being taken.
    """
    stop_distance = atr * stop_atr_multiplier
    stop_price = entry_price - stop_distance
    stop_percent = stop_distance / entry_price
    if stop_percent > max_stop_percent:
        return None
    return stop_price


def compute_take_profit(entry_price: Decimal, stop_price: Decimal, *, take_profit_r: Decimal) -> Decimal:
    """instrucao.md #30. R = entry - stop; take_profit = entry + take_profit_r * R."""
    r = entry_price - stop_price
    return entry_price + (take_profit_r * r)


def compute_quantity(
    *,
    risk_amount: Decimal,
    entry_price: Decimal,
    stop_price: Decimal,
    available_balance: Decimal,
    max_capital_allocation: Decimal,
    symbol_rules: SymbolRules,
) -> tuple[Decimal | None, list[str]]:
    """instrucao.md #28 — uses the smallest of every applicable limit.

    Never invents a quantity: any violated hard limit (below minQty, below
    minNotional) rejects the trade instead of silently bumping the quantity up.
    """
    reasons: list[str] = []

    risk_per_unit = entry_price - stop_price
    if risk_per_unit <= 0:
        return None, ["INVALID_RISK_PER_UNIT"]

    quantity_by_risk = risk_amount / risk_per_unit
    quantity_by_balance = available_balance / entry_price
    quantity_by_allocation = (available_balance * max_capital_allocation) / entry_price

    quantity = min(quantity_by_risk, quantity_by_balance, quantity_by_allocation, symbol_rules.max_qty)
    quantity = round_down_to_step(quantity, symbol_rules.step_size)

    if quantity < symbol_rules.min_qty:
        reasons.append("QUANTITY_BELOW_MIN_QTY")

    notional = quantity * entry_price
    if symbol_rules.min_notional is not None and notional < symbol_rules.min_notional:
        reasons.append("NOTIONAL_BELOW_MIN_NOTIONAL")
    if symbol_rules.max_notional is not None and notional > symbol_rules.max_notional:
        reasons.append("NOTIONAL_ABOVE_MAX_NOTIONAL")

    if reasons:
        return None, reasons
    return quantity, []
