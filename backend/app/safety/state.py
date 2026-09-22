"""BotState machine (instrucao.md #59, #80, #81). Persisted — never resets on restart.

States: STARTING, RECONCILING, WARMING_UP, READY, RUNNING, PAUSED, BLOCKED,
DEGRADED, EMERGENCY, STOPPED. Every transition is logged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import BotStateRecord, RiskEventRecord

logger = get_logger("safety.state")

VALID_STATES = {
    "STARTING", "RECONCILING", "WARMING_UP", "READY", "RUNNING",
    "PAUSED", "BLOCKED", "DEGRADED", "EMERGENCY", "STOPPED",
}


class BotStateService:
    def __init__(self, session: Session, *, symbol: str) -> None:
        self._session = session
        self._symbol = symbol

    def get_or_create(self) -> BotStateRecord:
        row = self._session.get(BotStateRecord, self._symbol)
        if row is None:
            row = BotStateRecord(
                symbol=self._symbol,
                state="STARTING",
                high_water_mark="0",
                daily_reference_equity="0",
                daily_reference_date="",
            )
            self._session.add(row)
            self._session.commit()
        return row

    def transition(self, new_state: str) -> BotStateRecord:
        if new_state not in VALID_STATES:
            raise ValueError(f"invalid bot state: {new_state}")
        row = self.get_or_create()
        old_state = row.state
        row.state = new_state
        row.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        logger.info(
            "bot_state_transition",
            extra={"context": {"symbol": self._symbol, "from": old_state, "to": new_state}},
        )
        return row

    def update_equity(self, current_equity: Decimal) -> BotStateRecord:
        """instrucao.md #80/#81 — high-water mark never resets; daily reference
        equity only rolls over on a new UTC day."""
        row = self.get_or_create()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if Decimal(row.high_water_mark) < current_equity:
            row.high_water_mark = str(current_equity)

        if row.daily_reference_date != today:
            row.daily_reference_date = today
            row.daily_reference_equity = str(current_equity)
            logger.info(
                "daily_reference_equity_rolled_over",
                extra={"context": {"symbol": self._symbol, "date": today, "equity": str(current_equity)}},
            )

        self._session.commit()
        return row

    def record_trade_result(self, realized_pnl: Decimal) -> BotStateRecord:
        row = self.get_or_create()
        if realized_pnl < 0:
            row.consecutive_losses += 1
        else:
            row.consecutive_losses = 0
        self._session.commit()
        return row

    def block_for_manual_resume(self, *, reason: str, event_type: str) -> BotStateRecord:
        """instrucao.md #37, #39 — MAX_CONSECUTIVE_LOSSES / MAX_DRAWDOWN require a human."""
        row = self.get_or_create()
        row.manual_resume_required = True
        row.block_reason = reason
        row.state = "BLOCKED"
        self._session.add(
            RiskEventRecord(event_type=event_type, details={"reason": reason}, manual_resume_required=True)
        )
        self._session.commit()
        logger.warning(
            "bot_blocked_manual_resume_required",
            extra={"context": {"symbol": self._symbol, "reason": reason}},
        )
        return row

    def manual_resume(self) -> BotStateRecord:
        row = self.get_or_create()
        row.manual_resume_required = False
        row.block_reason = None
        row.state = "READY"
        self._session.commit()
        logger.info("bot_manual_resume", extra={"context": {"symbol": self._symbol}})
        return row
