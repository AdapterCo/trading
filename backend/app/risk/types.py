"""RiskEngine inputs/outputs (instrucao.md #41).

RiskState is a read-only snapshot supplied by the caller (worker-execution, in
Fase 14) — RiskEngine never computes equity/positions/ledger itself, it only
judges the state it's given. This keeps RiskEngine decoupled from Position/Ledger
engines that don't exist yet (Fases 10-12).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskState:
    equity: Decimal
    high_water_mark: Decimal
    daily_reference_equity: Decimal

    open_positions_count: int
    consecutive_losses: int

    orders_sent_last_hour: int
    entries_sent_today: int

    candles_since_last_close: int | None  # None = never closed a position yet

    market_data_healthy: bool
    exchange_healthy: bool
    reconciled: bool
    has_conflicting_order: bool


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: list[str]
    quantity: Decimal | None = None
    stop_price: Decimal | None = None
    take_profit: Decimal | None = None
    risk_amount: Decimal | None = None
