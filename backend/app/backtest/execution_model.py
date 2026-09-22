"""BacktestExecutionModel (instrucao.md #98). Never assumes perfect execution.

Applies fees, spread and slippage, and respects the exact same symbol filters
(tick size, step size, min notional) as the real exchange — quantities are
rounded exactly like RiskEngine does in production (instrucao.md #43).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.exchange.types import SymbolRules
from app.risk.sizing import round_down_to_step


@dataclass(frozen=True)
class BacktestFill:
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_asset: str


class BacktestExecutionModel:
    def __init__(
        self,
        *,
        symbol_rules: SymbolRules,
        taker_fee_rate: Decimal,
        spread: Decimal,
        slippage: Decimal,
        quote_asset: str,
    ) -> None:
        self._rules = symbol_rules
        self._taker_fee_rate = taker_fee_rate
        self._spread = spread
        self._slippage = slippage
        self._quote_asset = quote_asset

    @property
    def rules(self) -> SymbolRules:
        return self._rules

    def market_order(self, *, side: str, reference_price: Decimal, requested_qty: Decimal) -> BacktestFill | None:
        """Returns None (NO FILL) when the order can't clear exchange minimums —
        never fabricates a fill that wouldn't actually have been accepted."""
        half_spread = reference_price * self._spread / 2
        slip = reference_price * self._slippage

        if side == "BUY":
            fill_price = reference_price + half_spread + slip  # buyer crosses the ask and pays slippage
        elif side == "SELL":
            fill_price = reference_price - half_spread - slip
        else:
            raise ValueError(f"unsupported side: {side}")

        quantity = round_down_to_step(requested_qty, self._rules.step_size)
        if quantity < self._rules.min_qty:
            return None

        notional = quantity * fill_price
        if self._rules.min_notional is not None and notional < self._rules.min_notional:
            return None

        fee = notional * self._taker_fee_rate
        return BacktestFill(price=fill_price, quantity=quantity, fee=fee, fee_asset=self._quote_asset)
