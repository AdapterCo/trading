"""ProtectionEngine (instrucao.md #31-#34). Protection has priority over new entries.

Priority order (#34): EMERGENCY > STOP > TAKE PROFIT > TRAILING > STRATEGY EXIT.
EMERGENCY is an external command (Fase 15/SafetyEngine), not decided here.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.db.models import PositionRecord


@dataclass(frozen=True)
class ProtectionResult:
    exit_action: str | None  # "STOP" | "TAKE_PROFIT" | "STRATEGY_EXIT" | None (no exit)
    new_stop_price: Decimal | None  # set when the stop should be updated, exit or not
    break_even_active: bool
    highest_price_since_entry: Decimal


def evaluate(
    position: PositionRecord,
    *,
    current_price: Decimal,
    atr_5m: Decimal,
    break_even_trigger_r: Decimal,
    trailing_start_r: Decimal,
    trailing_atr_multiplier: Decimal,
    strategic_exit_signal: bool,
) -> ProtectionResult:
    entry = Decimal(position.average_entry)
    initial_stop = Decimal(position.initial_stop_price)
    current_stop = Decimal(position.stop_price)
    take_profit = Decimal(position.take_profit)
    highest = max(Decimal(position.highest_price_since_entry), current_price)

    r = entry - initial_stop  # instrucao.md #27/#30 — R is always relative to the ORIGINAL stop
    break_even_active = bool(position.break_even_active)

    # --- Priority 1: STOP (instrucao.md #34) ---
    if current_price <= current_stop:
        return ProtectionResult("STOP", current_stop, break_even_active, highest)

    # --- Priority 2: TAKE PROFIT ---
    if current_price >= take_profit:
        return ProtectionResult("TAKE_PROFIT", current_stop, break_even_active, highest)

    new_stop = current_stop

    # --- Break-even (instrucao.md #31) — never moves the stop down ---
    if not break_even_active and r > 0 and current_price >= entry + break_even_trigger_r * r:
        break_even_active = True
        quantity = Decimal(position.quantity)
        # Economic break-even accounts for fees already paid — not a naive stop=entry (#31).
        fees_per_unit = Decimal(position.fees_total) / quantity if quantity else Decimal("0")
        new_stop = max(new_stop, entry + fees_per_unit)

    # --- Trailing stop (instrucao.md #32) — only ever rises, never below current stop ---
    if r > 0 and current_price >= entry + trailing_start_r * r:
        trailing_candidate = highest - (atr_5m * trailing_atr_multiplier)
        new_stop = max(new_stop, trailing_candidate)

    if new_stop != current_stop:
        return ProtectionResult(None, new_stop, break_even_active, highest)

    # --- Priority 4 (lowest): STRATEGY EXIT, from Strategy's own signal ---
    if strategic_exit_signal:
        return ProtectionResult("STRATEGY_EXIT", current_stop, break_even_active, highest)

    return ProtectionResult(None, None, break_even_active, highest)
