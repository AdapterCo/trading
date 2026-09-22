"""PositionEngine (instrucao.md #50, #51). Position derives from fills, never from OrderIntent alone."""
from __future__ import annotations

from decimal import Decimal

from app.db.models import PositionRecord
from app.exchange.types import TradeFill
from app.execution.fills import compute_vwap, total_commission_in_asset
from app.positions.repository import PositionRepository


class PositionEngine:
    def __init__(self, repository: PositionRepository) -> None:
        self._repository = repository

    def open_from_fills(
        self,
        *,
        symbol: str,
        fills: list[TradeFill],
        stop_price: Decimal,
        take_profit: Decimal,
        fee_asset: str,
    ) -> PositionRecord:
        """instrucao.md #49 — uses only executed_quantity (sum of actual fills),
        never the originally requested OrderIntent quantity."""
        average_entry, quantity = compute_vwap(fills)
        if quantity == 0:
            raise ValueError("cannot open a position with zero executed quantity")

        fees_total = total_commission_in_asset(fills, fee_asset)
        cost_basis = average_entry * quantity

        return self._repository.create(
            symbol=symbol,
            quantity=quantity,
            average_entry=average_entry,
            cost_basis=cost_basis,
            fees_total=fees_total,
            stop_price=stop_price,
            take_profit=take_profit,
        )

    def unrealized_pnl(self, position: PositionRecord, current_price: Decimal) -> Decimal:
        quantity = Decimal(position.quantity)
        entry = Decimal(position.average_entry)
        fees = Decimal(position.fees_total)
        return (current_price - entry) * quantity - fees

    def market_value(self, position: PositionRecord, current_price: Decimal) -> Decimal:
        return Decimal(position.quantity) * current_price
