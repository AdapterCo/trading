"""Persistence for Signal and OrderIntent (instrucao.md #25, #42, #71).

Every Strategy evaluation is persisted, including HOLD. An OrderIntent is
persisted with its client_order_id BEFORE any order is sent (Fase 8) — that
ordering is what makes the later retry/idempotency policy possible (#45, #46).
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import OrderIntentRecord, SignalRecord
from app.orders.client_order_id import generate_client_order_id
from app.risk.types import RiskDecision
from app.strategy.types import Signal


class SignalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, signal: Signal) -> SignalRecord:
        row = SignalRecord(
            id=signal.id,
            symbol=signal.symbol,
            strategy=signal.strategy,
            strategy_version=signal.strategy_version,
            decision=signal.decision.value,
            reference_price=str(signal.reference_price),
            candle_open_time=signal.candle_open_time,
            reasons=signal.reasons,
            indicator_snapshot=_json_safe(signal.indicator_snapshot),
        )
        self._session.add(row)
        self._session.commit()
        return row


class OrderIntentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_from_decision(
        self, *, signal: Signal, decision: RiskDecision, settings: Settings, side: str = "BUY", order_type: str = "MARKET"
    ) -> OrderIntentRecord:
        if not decision.approved:
            raise ValueError("cannot create an OrderIntent from a rejected RiskDecision")

        row = OrderIntentRecord(
            signal_id=signal.id,
            strategy_version=signal.strategy_version,
            config_version=settings.config_version,
            symbol=signal.symbol,
            side=side,
            order_type=order_type,
            quantity=str(decision.quantity),
            expected_price=str(signal.reference_price),
            stop_price=str(decision.stop_price),
            take_profit=str(decision.take_profit),
            risk_amount=str(decision.risk_amount),
            client_order_id=generate_client_order_id(),
            status="CREATED",
        )
        # Persist BEFORE any order is sent — required for idempotent retry (#45, #46).
        self._session.add(row)
        self._session.commit()
        return row

    def get_by_client_order_id(self, client_order_id: str) -> OrderIntentRecord | None:
        return (
            self._session.query(OrderIntentRecord)
            .filter_by(client_order_id=client_order_id)
            .one_or_none()
        )


def _json_safe(value: dict) -> dict:
    """FeatureSnapshot dicts may contain Decimal-free floats already, but guard
    against any accidental Decimal leaking in since JSON can't serialize it."""
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in value.items()}
