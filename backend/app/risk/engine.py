"""RiskEngine (instrucao.md #41). Strategy can propose BUY; RiskEngine's verdict is final.

Every gate from the "EXECUÇÃO" checklist in #24 is evaluated and every failure is
collected — nothing here silently approves when the state is unknown/degraded
(instrucao.md #116: UNKNOWN -> block).
"""
from __future__ import annotations

from decimal import Decimal

from app.core.config import Settings
from app.exchange.types import AccountInfo, BestBidAsk, SymbolRules
from app.features.spread import compute_spread
from app.risk.sizing import compute_quantity, compute_stop_price, compute_take_profit
from app.risk.types import RiskDecision, RiskState


class RiskEngine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def evaluate_buy(
        self,
        *,
        entry_price: Decimal,
        atr_5m: Decimal,
        symbol_rules: SymbolRules,
        account: AccountInfo,
        quote: BestBidAsk,
        state: RiskState,
    ) -> RiskDecision:
        s = self._settings
        reasons: list[str] = []

        # --- Execution readiness gates (instrucao.md #24 "EXECUÇÃO" section) ---
        spread = compute_spread(quote)
        if spread is None:
            reasons.append("SPREAD_UNAVAILABLE")
        elif spread > Decimal(str(s.max_spread)):
            reasons.append("SPREAD_TOO_WIDE")

        if not state.market_data_healthy:
            reasons.append("MARKET_DATA_NOT_HEALTHY")
        if not state.exchange_healthy:
            reasons.append("EXCHANGE_NOT_CONNECTED")
        if not state.reconciled:
            reasons.append("ACCOUNT_NOT_RECONCILED")
        if not account.can_trade:
            reasons.append("ACCOUNT_CANNOT_TRADE")
        if state.open_positions_count >= s.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_REACHED")
        if state.has_conflicting_order:
            reasons.append("CONFLICTING_ORDER_EXISTS")
        if state.candles_since_last_close is not None and state.candles_since_last_close < s.cooldown_candles:
            reasons.append("COOLDOWN_ACTIVE")

        # --- Risk limits (instrucao.md #37-#40) ---
        if state.consecutive_losses >= s.max_consecutive_losses:
            reasons.append("CONSECUTIVE_LOSS_LIMIT_REACHED")

        if state.daily_reference_equity > 0:
            daily_loss_pct = (state.daily_reference_equity - state.equity) / state.daily_reference_equity
            if daily_loss_pct >= Decimal(str(s.max_daily_loss)):
                reasons.append("DAILY_LOSS_LIMIT_REACHED")

        if state.high_water_mark > 0:
            drawdown_pct = (state.high_water_mark - state.equity) / state.high_water_mark
            if drawdown_pct >= Decimal(str(s.max_drawdown)):
                reasons.append("DRAWDOWN_LIMIT_REACHED")

        if state.orders_sent_last_hour >= s.max_orders_per_hour:
            reasons.append("MAX_ORDERS_PER_HOUR_REACHED")
        if state.entries_sent_today >= s.max_entries_per_day:
            reasons.append("MAX_ENTRIES_PER_DAY_REACHED")

        # --- Stop / sizing (instrucao.md #26-#29) ---
        stop_price = compute_stop_price(
            entry_price,
            atr_5m,
            stop_atr_multiplier=Decimal(str(s.stop_atr_multiplier)),
            max_stop_percent=Decimal(str(s.max_stop_percent)),
        )
        if stop_price is None:
            reasons.append("STOP_EXCEEDS_MAX_STOP_PERCENT")
            return RiskDecision(approved=False, reasons=reasons)

        if reasons:
            return RiskDecision(approved=False, reasons=reasons)

        risk_amount = state.equity * Decimal(str(s.risk_per_trade))
        available_balance = next(
            (b.free for b in account.balances if b.asset == s.quote_asset), Decimal("0")
        )

        quantity, sizing_reasons = compute_quantity(
            risk_amount=risk_amount,
            entry_price=entry_price,
            stop_price=stop_price,
            available_balance=available_balance,
            max_capital_allocation=Decimal(str(s.max_capital_allocation)),
            symbol_rules=symbol_rules,
        )
        if sizing_reasons:
            return RiskDecision(approved=False, reasons=sizing_reasons, risk_amount=risk_amount, stop_price=stop_price)

        take_profit = compute_take_profit(entry_price, stop_price, take_profit_r=Decimal(str(s.take_profit_r)))

        return RiskDecision(
            approved=True,
            reasons=[],
            quantity=quantity,
            stop_price=stop_price,
            take_profit=take_profit,
            risk_amount=risk_amount,
        )
