"""Position persistence (instrucao.md #50, #82)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import PositionRecord, TradeRecord


class PositionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_open(self, symbol: str) -> PositionRecord | None:
        return (
            self._session.query(PositionRecord)
            .filter_by(symbol=symbol, status="OPEN")
            .one_or_none()
        )

    def count_open(self, symbol: str | None = None) -> int:
        q = self._session.query(PositionRecord).filter_by(status="OPEN")
        if symbol is not None:
            q = q.filter_by(symbol=symbol)
        return q.count()

    def create(
        self,
        *,
        symbol: str,
        quantity: Decimal,
        average_entry: Decimal,
        cost_basis: Decimal,
        fees_total: Decimal,
        stop_price: Decimal,
        take_profit: Decimal,
    ) -> PositionRecord:
        row = PositionRecord(
            symbol=symbol,
            status="OPEN",
            quantity=str(quantity),
            average_entry=str(average_entry),
            cost_basis=str(cost_basis),
            fees_total=str(fees_total),
            initial_stop_price=str(stop_price),
            stop_price=str(stop_price),
            take_profit=str(take_profit),
            break_even_active=False,
            highest_price_since_entry=str(average_entry),
        )
        self._session.add(row)
        self._session.commit()
        return row

    def save(self, position: PositionRecord) -> None:
        self._session.commit()

    def close(
        self, position: PositionRecord, *, exit_price: Decimal, exit_fees: Decimal, exit_reason: str
    ) -> TradeRecord:
        quantity = Decimal(position.quantity)
        entry_price = Decimal(position.average_entry)
        entry_fees = Decimal(position.fees_total)
        total_fees = entry_fees + exit_fees

        realized_pnl = (exit_price - entry_price) * quantity - total_fees

        position.status = "CLOSED"
        position.realized_pnl = str(realized_pnl)
        position.closed_at = datetime.now(timezone.utc)

        trade = TradeRecord(
            position_id=position.id,
            symbol=position.symbol,
            entry_price=str(entry_price),
            exit_price=str(exit_price),
            quantity=str(quantity),
            fees_total=str(total_fees),
            realized_pnl=str(realized_pnl),
            exit_reason=exit_reason,
            opened_at=position.opened_at,
            closed_at=position.closed_at,
        )
        self._session.add(trade)
        self._session.commit()
        return trade
