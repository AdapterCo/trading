"""Persistence for exchange orders (instrucao.md #82)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ExchangeOrderRecord
from app.exchange.types import OrderInfo


class ExchangeOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_client_order_id(self, client_order_id: str) -> ExchangeOrderRecord | None:
        return (
            self._session.query(ExchangeOrderRecord)
            .filter_by(client_order_id=client_order_id)
            .one_or_none()
        )

    def upsert_from_order_info(self, order_intent_id: str, info: OrderInfo) -> ExchangeOrderRecord:
        """Idempotent by client_order_id — a retry that reconciles with an order
        that already exists on the exchange must update, never duplicate (#46)."""
        existing = self.get_by_client_order_id(info.client_order_id)
        if existing is not None:
            existing.exchange_order_id = info.exchange_order_id
            existing.status = info.status
            existing.price = str(info.price)
            existing.orig_qty = str(info.orig_qty)
            existing.executed_qty = str(info.executed_qty)
            existing.updated_at = datetime.now(timezone.utc)
            self._session.commit()
            return existing

        row = ExchangeOrderRecord(
            order_intent_id=order_intent_id,
            exchange_order_id=info.exchange_order_id,
            client_order_id=info.client_order_id,
            symbol=info.symbol,
            side=info.side,
            order_type=info.order_type,
            status=info.status,
            price=str(info.price),
            orig_qty=str(info.orig_qty),
            executed_qty=str(info.executed_qty),
        )
        self._session.add(row)
        self._session.commit()
        return row
