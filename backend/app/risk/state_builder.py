"""Assembles RiskState/equity from persisted state (instrucao.md #41, #79-#81).

Kept separate from RiskEngine itself so RiskEngine stays a pure, stateless judge —
only this module touches the database to gather the numbers it judges.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import BotStateRecord, ExchangeOrderRecord, OrderIntentRecord, PositionRecord
from app.exchange.types import AccountInfo
from app.market_data.intervals import interval_ms
from app.risk.types import RiskState


def compute_equity(account: AccountInfo, position: PositionRecord | None, current_price: Decimal, quote_asset: str) -> Decimal:
    """instrucao.md #79 — equity = quote balance + market value of assets the bot controls."""
    cash = next((b.free + b.locked for b in account.balances if b.asset == quote_asset), Decimal("0"))
    market_value = Decimal(position.quantity) * current_price if position is not None else Decimal("0")
    return cash + market_value


def build_risk_state(
    *,
    session: Session,
    symbol: str,
    position: PositionRecord | None,
    bot_state: BotStateRecord,
    equity: Decimal,
    market_data_healthy: bool,
    exchange_healthy: bool,
    reconciled: bool,
    has_conflicting_order: bool,
    entry_interval: str,
) -> RiskState:
    now = datetime.now(timezone.utc)

    orders_last_hour = (
        session.query(ExchangeOrderRecord)
        .filter(ExchangeOrderRecord.created_at >= now - timedelta(hours=1))
        .count()
    )

    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    entries_today = (
        session.query(OrderIntentRecord)
        .filter(OrderIntentRecord.side == "BUY", OrderIntentRecord.created_at >= today_start)
        .count()
    )

    candles_since_last_close = None
    last_closed = (
        session.query(PositionRecord)
        .filter_by(symbol=symbol, status="CLOSED")
        .order_by(PositionRecord.closed_at.desc())
        .first()
    )
    if last_closed is not None and last_closed.closed_at is not None:
        elapsed_ms = (now - last_closed.closed_at).total_seconds() * 1000
        candles_since_last_close = int(elapsed_ms // interval_ms(entry_interval))

    return RiskState(
        equity=equity,
        high_water_mark=Decimal(bot_state.high_water_mark),
        daily_reference_equity=Decimal(bot_state.daily_reference_equity),
        open_positions_count=1 if position is not None else 0,
        consecutive_losses=bot_state.consecutive_losses,
        orders_sent_last_hour=orders_last_hour,
        entries_sent_today=entries_today,
        candles_since_last_close=candles_since_last_close,
        market_data_healthy=market_data_healthy,
        exchange_healthy=exchange_healthy,
        reconciled=reconciled,
        has_conflicting_order=has_conflicting_order,
    )
