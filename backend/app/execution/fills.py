"""Fill processing (instrucao.md #48, #49).

Never assumes full execution — everything downstream (PositionEngine) must use
executed_quantity, and partial fills are the normal case, not an edge case.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import FillRecord
from app.exchange.types import OrderInfo, TradeFill


class FillRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, exchange_order_record_id: str, fill: TradeFill) -> FillRecord:
        """Idempotent by exchange_trade_id — reconciliation can call this repeatedly."""
        existing = (
            self._session.query(FillRecord)
            .filter_by(exchange_trade_id=fill.exchange_trade_id)
            .one_or_none()
        )
        if existing is not None:
            return existing

        row = FillRecord(
            exchange_order_record_id=exchange_order_record_id,
            exchange_trade_id=fill.exchange_trade_id,
            exchange_order_id=fill.exchange_order_id,
            symbol=fill.symbol,
            price=str(fill.price),
            quantity=str(fill.quantity),
            commission=str(fill.commission),
            commission_asset=fill.commission_asset,
            is_buyer=fill.is_buyer,
            timestamp=fill.timestamp,
        )
        self._session.add(row)
        self._session.commit()
        return row

    def get_for_order(self, exchange_order_id: str) -> list[FillRecord]:
        return (
            self._session.query(FillRecord)
            .filter_by(exchange_order_id=exchange_order_id)
            .order_by(FillRecord.timestamp)
            .all()
        )


def compute_vwap(fills: list[TradeFill]) -> tuple[Decimal, Decimal]:
    """instrucao.md #48 — volume-weighted average price. Returns (avg_price, total_qty).

    Never invents a price when there are no fills — caller must handle the empty case.
    """
    total_qty = sum((f.quantity for f in fills), Decimal("0"))
    if total_qty == 0:
        return Decimal("0"), Decimal("0")
    weighted_sum = sum((f.price * f.quantity for f in fills), Decimal("0"))
    return weighted_sum / total_qty, total_qty


def total_commission_in_asset(fills: list[TradeFill], asset: str) -> Decimal:
    return sum((f.commission for f in fills if f.commission_asset == asset), Decimal("0"))


def extract_fills_from_order_info(info: OrderInfo) -> list[TradeFill]:
    """The inline `fills` array on a create_order response has no per-fill timestamp
    or is_buyer flag — approximated here from the order itself. For an authoritative
    per-fill record (e.g. during reconciliation) use ExchangeAdapter.get_trades instead."""
    raw_fills = info.raw.get("fills") or []
    is_buyer = info.side == "BUY"
    return [
        TradeFill(
            exchange_trade_id=str(f["tradeId"]),
            exchange_order_id=info.exchange_order_id,
            symbol=info.symbol,
            price=Decimal(str(f["price"])),
            quantity=Decimal(str(f["qty"])),
            commission=Decimal(str(f["commission"])),
            commission_asset=f["commissionAsset"],
            is_buyer=is_buyer,
            timestamp=info.update_time,
        )
        for f in raw_fills
    ]
