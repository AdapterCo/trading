"""ReconciliationEngine (instrucao.md #55, #56).

The exchange is the authoritative source of truth for external state. This never
opens a position based on the database alone — it always compares against what
the exchange actually reports, and blocks trading when the two disagree.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import ReconciliationLogRecord
from app.exchange.base import ExchangeAdapter
from app.positions.repository import PositionRepository

logger = get_logger("reconciliation.engine")

# Dust tolerance for base-asset quantity comparisons — exchange rounding/fees can
# leave sub-step-size residue that must never be mistaken for an inconsistency.
DEFAULT_TOLERANCE = Decimal("0.00000010")


@dataclass(frozen=True)
class ReconciliationResult:
    consistent: bool
    difference: dict
    resolution: str


class ReconciliationEngine:
    def __init__(self, session: Session, exchange: ExchangeAdapter, position_repo: PositionRepository) -> None:
        self._session = session
        self._exchange = exchange
        self._position_repo = position_repo

    def reconcile(self, *, symbol: str, base_asset: str, log_type: str = "periodic") -> ReconciliationResult:
        account = self._exchange.get_account()
        exchange_balance = next(
            (b.free + b.locked for b in account.balances if b.asset == base_asset), Decimal("0")
        )

        position = self._position_repo.get_open(symbol)
        internal_quantity = Decimal(position.quantity) if position is not None else Decimal("0")

        diff = exchange_balance - internal_quantity
        consistent = abs(diff) <= DEFAULT_TOLERANCE

        internal_state = {"open_position_quantity": str(internal_quantity)}
        exchange_state = {"balance": str(exchange_balance)}
        difference = {"delta": str(diff)}
        resolution = (
            "consistent within dust tolerance"
            if consistent
            else "BLOCKED: internal position does not match exchange balance"
        )

        log_row = ReconciliationLogRecord(
            type=log_type,
            internal_state=internal_state,
            exchange_state=exchange_state,
            difference=difference,
            resolution=resolution,
            status="CONSISTENT" if consistent else "BLOCKED",
        )
        self._session.add(log_row)
        self._session.commit()

        if not consistent:
            logger.warning(
                "reconciliation_inconsistent",
                extra={"context": {"symbol": symbol, "delta": str(diff)}},
            )

        return ReconciliationResult(consistent=consistent, difference=difference, resolution=resolution)
