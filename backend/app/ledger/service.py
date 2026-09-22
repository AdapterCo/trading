"""LedgerService (instrucao.md #54). Append-only — no update/delete method exists here
on purpose. Corrections must be new ADJUSTMENT rows, never edits to history.

Convention (not fully specified by instrucao.md, documented here for audit clarity):
- BUY entry: asset=quote_asset, amount=-(price*qty) — cash spent acquiring the base asset.
- SELL entry: asset=quote_asset, amount=+(price*qty) — cash received disposing of it.
- FEE entry: asset=commission_asset, amount=-commission, one per fill.
- REALIZED_PNL entry: asset=quote_asset, amount=realized_pnl, recorded when a position closes.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import LedgerEntryRecord
from app.exchange.types import TradeFill


class LedgerService:
    def __init__(self, session: Session, *, quote_asset: str) -> None:
        self._session = session
        self._quote_asset = quote_asset

    def record_fill(self, *, symbol: str, side: str, fill: TradeFill, position_id: str | None) -> None:
        if side not in ("BUY", "SELL"):
            raise ValueError(f"unsupported ledger side: {side}")

        cash_amount = fill.price * fill.quantity
        if side == "BUY":
            cash_amount = -cash_amount

        self._session.add(
            LedgerEntryRecord(
                event_type=side,
                symbol=symbol,
                asset=self._quote_asset,
                amount=str(cash_amount),
                position_id=position_id,
                reference_id=fill.exchange_trade_id,
            )
        )

        if fill.commission != 0:
            self._session.add(
                LedgerEntryRecord(
                    event_type="FEE",
                    symbol=symbol,
                    asset=fill.commission_asset,
                    amount=str(-fill.commission),
                    position_id=position_id,
                    reference_id=fill.exchange_trade_id,
                )
            )

        self._session.commit()

    def record_realized_pnl(self, *, symbol: str, position_id: str, realized_pnl: Decimal) -> None:
        self._session.add(
            LedgerEntryRecord(
                event_type="REALIZED_PNL",
                symbol=symbol,
                asset=self._quote_asset,
                amount=str(realized_pnl),
                position_id=position_id,
                reference_id=None,
            )
        )
        self._session.commit()

    def record_adjustment(self, *, symbol: str, asset: str, amount: Decimal, note: str, reference_id: str | None = None) -> None:
        """instrucao.md #54 — the ONLY way to correct a past error: never edit, only append."""
        self._session.add(
            LedgerEntryRecord(
                event_type="ADJUSTMENT",
                symbol=symbol,
                asset=asset,
                amount=str(amount),
                reference_id=reference_id,
                note=note,
            )
        )
        self._session.commit()

    def entries_for_symbol(self, symbol: str) -> list[LedgerEntryRecord]:
        return (
            self._session.query(LedgerEntryRecord)
            .filter_by(symbol=symbol)
            .order_by(LedgerEntryRecord.created_at)
            .all()
        )
