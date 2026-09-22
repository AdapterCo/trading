"""worker-execution (instrucao.md #52, Fase 14). Runs continuously as its own process,
never inside a FastAPI request. Orchestrates the full loop from instrucao.md #2/#52:

MARKET DATA -> STRATEGY -> SIGNAL -> RISK -> ORDER INTENT -> EXECUTION -> FILLS
-> POSITION -> PROTECTION -> LEDGER -> METRICS -> RECONCILIATION
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

from app.alerts.service import AlertService
from app.core.config import Settings, TradingMode, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import SessionLocal
from app.exchange.base import ExchangeAdapter
from app.exchange.binance_adapter import BinanceExchangeAdapter
from app.execution.fills import FillRepository, fill_record_to_trade_fill
from app.execution.paper_sender import PaperOrderSender
from app.execution.repository import ExchangeOrderRepository
from app.execution.sender import OrderSendError, OrderSender
from app.features.engine import FeatureEngine
from app.ledger.service import LedgerService
from app.market_data.stream import KlineStreamListener
from app.orders.repository import OrderIntentRepository, SignalRepository
from app.positions.engine import PositionEngine
from app.positions.protection import evaluate as evaluate_protection
from app.positions.repository import PositionRepository
from app.reconciliation.engine import ReconciliationEngine
from app.risk.engine import RiskEngine
from app.risk.state_builder import build_risk_state, compute_equity
from app.safety.state import BotStateService
from app.strategy.trend_pullback_v1 import TrendPullbackV1
from app.strategy.types import SignalDecision, StrategyContext

logger = get_logger("worker.execution")


class ExecutionWorker:
    def __init__(self, settings: Settings, exchange: ExchangeAdapter | None = None) -> None:
        self._settings = settings
        self._exchange = exchange or BinanceExchangeAdapter(settings)
        self._alerts = AlertService(settings.alert_webhook_url)
        self._strategy = TrendPullbackV1()
        self._risk_engine = RiskEngine(settings)
        self._feature_engine = FeatureEngine()
        self._last_reconciliation_ok = False

    def _make_sender(self, order_repo: ExchangeOrderRepository, fill_repo: FillRepository):
        """instrucao.md #5 — only LIVE ever reaches the real exchange's order endpoint.
        Every other mode simulates against real, read-only market data instead."""
        if self._settings.trading_mode is TradingMode.LIVE:
            return OrderSender(self._exchange, order_repo, fill_repo)
        return PaperOrderSender(self._exchange, order_repo, fill_repo, quote_asset=self._settings.quote_asset)

    def startup(self) -> None:
        """instrucao.md #55, #58 — block trading until reconciled."""
        session = SessionLocal()
        try:
            bot_state = BotStateService(session, symbol=self._settings.symbol)
            bot_state.transition("RECONCILING")

            result = ReconciliationEngine(session, self._exchange, PositionRepository(session)).reconcile(
                symbol=self._settings.symbol, base_asset=self._settings.base_asset, log_type="startup"
            )
            self._last_reconciliation_ok = result.consistent
            bot_state.transition("READY" if result.consistent else "BLOCKED")
            logger.info(
                "worker_execution_startup",
                extra={"context": {"symbol": self._settings.symbol, "reconciled": result.consistent}},
            )
            if not result.consistent:
                self._alerts.send(
                    "RECONCILIATION_ERROR", f"startup reconciliation failed: {result.resolution}",
                    context={"symbol": self._settings.symbol},
                )
        finally:
            session.close()

    def handle_closed_candle(self, candle_5m) -> None:
        """One full pass of the pipeline for a single closed entry-timeframe candle."""
        session = SessionLocal()
        try:
            self._run_cycle(session, candle_5m)
        finally:
            session.close()

    def _run_cycle(self, session, candle_5m) -> None:
        s = self._settings
        bot_state_service = BotStateService(session, symbol=s.symbol)
        bot_state = bot_state_service.get_or_create()

        # instrucao.md #38/#62 — a block/pause stops NEW entries only. An existing
        # position keeps its protection running regardless (never abandoned).
        entries_blocked = bot_state.manual_resume_required or bot_state.state in ("PAUSED", "BLOCKED", "EMERGENCY", "STOPPED")

        position_repo = PositionRepository(session)
        position = position_repo.get_open(s.symbol)

        account = self._exchange.get_account()
        current_price = candle_5m.close
        equity = compute_equity(account, position, current_price, s.quote_asset)
        bot_state_service.update_equity(equity)

        c1h = self._exchange.get_klines(s.symbol, s.macro_interval, limit=250)
        c15m = self._exchange.get_klines(s.symbol, s.trend_interval, limit=250)
        c5m = self._exchange.get_klines(s.symbol, s.entry_interval, limit=250)
        c5m = _ensure_current_candle_included(c5m, candle_5m)

        f1h = self._feature_engine.compute_latest(c1h)
        f15m = self._feature_engine.compute_latest(c15m)
        f5m_series = self._feature_engine.compute_series(c5m)
        f5m_current = f5m_series[-1] if f5m_series else None

        if position is not None:
            self._manage_open_position(
                session, bot_state_service, position_repo, position, candle_5m, f5m_current, f1h, f15m, f5m_series
            )
            return

        if entries_blocked:
            logger.info("worker_new_entries_blocked", extra={"context": {"symbol": s.symbol, "state": bot_state.state}})
            return

        self._evaluate_entry(
            session, bot_state_service, position_repo, account, candle_5m, f1h, f15m, f5m_series, equity, bot_state
        )

    def _manage_open_position(
        self, session, bot_state_service, position_repo, position, candle_5m, f5m_current, f1h, f15m, f5m_series
    ) -> None:
        s = self._settings
        context = StrategyContext(
            feature_1h=f1h, feature_15m=f15m, features_5m=f5m_series,
            adx_min=s.adx_min, rsi_entry_min=s.rsi_entry_min, rsi_entry_max=s.rsi_entry_max,
            pullback_max_distance=s.pullback_max_distance, min_volume_ratio=s.min_volume_ratio,
            min_taker_buy_ratio=s.min_taker_buy_ratio,
        )
        strategy_signal = self._strategy.on_candle(candle_5m.open_time, context)
        SignalRepository(session).save(strategy_signal)

        atr_5m = Decimal(str(f5m_current.atr14)) if f5m_current and f5m_current.atr14 is not None else Decimal("0")
        protection = evaluate_protection(
            position,
            current_price=candle_5m.close,
            atr_5m=atr_5m,
            break_even_trigger_r=Decimal(str(s.break_even_trigger_r)),
            trailing_start_r=Decimal(str(s.trailing_start_r)),
            trailing_atr_multiplier=Decimal(str(s.trailing_atr_multiplier)),
            strategic_exit_signal=(strategy_signal.decision == SignalDecision.EXIT),
        )

        if protection.exit_action is not None:
            self._exit_position(session, bot_state_service, position_repo, position, protection.exit_action)
            return

        if protection.new_stop_price is not None:
            position.stop_price = str(protection.new_stop_price)
            position.break_even_active = protection.break_even_active
            position.highest_price_since_entry = str(protection.highest_price_since_entry)
            position_repo.save(position)

    def _exit_position(self, session, bot_state_service, position_repo, position, exit_reason: str) -> None:
        s = self._settings
        intent_repo = OrderIntentRepository(session)
        order_repo = ExchangeOrderRepository(session)
        fill_repo = FillRepository(session)
        ledger = LedgerService(session, quote_asset=s.quote_asset)
        sender = self._make_sender(order_repo, fill_repo)

        from app.risk.types import RiskDecision
        from app.strategy.types import Signal

        exit_signal = Signal(
            symbol=s.symbol, strategy=self._strategy.name, strategy_version=self._strategy.version,
            decision=SignalDecision.EXIT, reference_price=float(position.average_entry),
            candle_open_time=0, reasons=[exit_reason], indicator_snapshot={},
        )
        SignalRepository(session).save(exit_signal)

        decision = RiskDecision(
            approved=True, reasons=[], quantity=Decimal(position.quantity),
            stop_price=Decimal(position.stop_price), take_profit=Decimal(position.take_profit),
            risk_amount=Decimal("0"),
        )
        intent = intent_repo.create_from_decision(
            signal=exit_signal, decision=decision, settings=s, side="SELL", order_type="MARKET"
        )

        try:
            order_row = sender.send(intent)
        except OrderSendError:
            logger.error("exit_order_send_failed_blocking", extra={"context": {"symbol": s.symbol}})
            bot_state_service.transition("BLOCKED")
            self._alerts.send("ORDER_ERROR", "exit order send failed after retry", context={"symbol": s.symbol})
            return

        fills = [fill_record_to_trade_fill(f) for f in fill_repo.get_for_order(order_row.exchange_order_id)]
        for fill in fills:
            ledger.record_fill(symbol=s.symbol, side="SELL", fill=fill, position_id=position.id)

        exit_fees = sum((f.commission for f in fills if f.commission_asset == s.quote_asset), Decimal("0"))
        avg_exit_price, _ = _vwap(fills) if fills else (Decimal(order_row.price), Decimal("0"))
        trade = position_repo.close(position, exit_price=avg_exit_price, exit_fees=exit_fees, exit_reason=exit_reason)

        ledger.record_realized_pnl(symbol=s.symbol, position_id=position.id, realized_pnl=Decimal(trade.realized_pnl))
        bot_state_service.record_trade_result(Decimal(trade.realized_pnl))

        # Position is now closed — refetch the account to get real post-trade equity,
        # rather than reusing a stale pre-trade number, before judging drawdown (#39).
        account_after = self._exchange.get_account()
        equity_after = compute_equity(account_after, None, avg_exit_price, s.quote_asset)
        updated = bot_state_service.update_equity(equity_after)

        if updated.consecutive_losses >= s.max_consecutive_losses:
            reason = f"{updated.consecutive_losses} consecutive losses"
            bot_state_service.block_for_manual_resume(reason=reason, event_type="CONSECUTIVE_LOSS_LIMIT")
            self._alerts.send("CONSECUTIVE_LOSS_LIMIT", reason, context={"symbol": s.symbol})

        if Decimal(updated.high_water_mark) > 0:
            drawdown_pct = (Decimal(updated.high_water_mark) - equity_after) / Decimal(updated.high_water_mark)
            if drawdown_pct >= Decimal(str(s.max_drawdown)):
                bot_state_service.block_for_manual_resume(reason="drawdown limit reached", event_type="DRAWDOWN_LIMIT")
                self._alerts.send("DRAWDOWN_LIMIT", f"drawdown {drawdown_pct:.2%} reached", context={"symbol": s.symbol})

        logger.info(
            "position_closed",
            extra={"context": {"symbol": s.symbol, "reason": exit_reason, "realized_pnl": str(trade.realized_pnl)}},
        )

    def _evaluate_entry(
        self, session, bot_state_service, position_repo, account, candle_5m, f1h, f15m, f5m_series, equity, bot_state
    ) -> None:
        s = self._settings
        context = StrategyContext(
            feature_1h=f1h, feature_15m=f15m, features_5m=f5m_series,
            adx_min=s.adx_min, rsi_entry_min=s.rsi_entry_min, rsi_entry_max=s.rsi_entry_max,
            pullback_max_distance=s.pullback_max_distance, min_volume_ratio=s.min_volume_ratio,
            min_taker_buy_ratio=s.min_taker_buy_ratio,
        )
        signal = self._strategy.on_candle(candle_5m.open_time, context)
        SignalRepository(session).save(signal)

        if signal.decision != SignalDecision.BUY:
            return

        f5m_current = f5m_series[-1]
        symbol_rules = self._exchange.get_symbol_info(s.symbol)
        quote = self._exchange.get_best_bid_ask(s.symbol)
        atr_5m = Decimal(str(f5m_current.atr14)) if f5m_current.atr14 is not None else Decimal("0")

        risk_state = build_risk_state(
            session=session, symbol=s.symbol, position=None, bot_state=bot_state, equity=equity,
            market_data_healthy=True, exchange_healthy=True, reconciled=self._last_reconciliation_ok,
            has_conflicting_order=False, entry_interval=s.entry_interval,
        )
        decision = self._risk_engine.evaluate_buy(
            entry_price=candle_5m.close, atr_5m=atr_5m, symbol_rules=symbol_rules,
            account=account, quote=quote, state=risk_state,
        )

        if not decision.approved:
            logger.info("buy_rejected_by_risk_engine", extra={"context": {"symbol": s.symbol, "reasons": decision.reasons}})
            return

        intent = OrderIntentRepository(session).create_from_decision(
            signal=signal, decision=decision, settings=s, side="BUY", order_type="MARKET"
        )
        fill_repo = FillRepository(session)
        sender = self._make_sender(ExchangeOrderRepository(session), fill_repo)
        try:
            order_row = sender.send(intent)
        except OrderSendError:
            logger.error("entry_order_send_failed_blocking", extra={"context": {"symbol": s.symbol}})
            bot_state_service.transition("BLOCKED")
            self._alerts.send("ORDER_ERROR", "entry order send failed after retry", context={"symbol": s.symbol})
            return

        fills = [fill_record_to_trade_fill(f) for f in fill_repo.get_for_order(order_row.exchange_order_id)]
        if not fills:
            logger.warning("entry_order_no_fills_yet", extra={"context": {"client_order_id": intent.client_order_id}})
            return

        ledger = LedgerService(session, quote_asset=s.quote_asset)
        for fill in fills:
            ledger.record_fill(symbol=s.symbol, side="BUY", fill=fill, position_id=None)

        position = PositionEngine(position_repo).open_from_fills(
            symbol=s.symbol, fills=fills, stop_price=decision.stop_price, take_profit=decision.take_profit,
            fee_asset=s.quote_asset,
        )
        logger.info("position_opened", extra={"context": {"symbol": s.symbol, "quantity": position.quantity}})

    # --- Safety controls (instrucao.md #62-#64, Fase 15) ---

    def pause(self) -> None:
        """instrucao.md #62 — blocks new entries, preserves any open position/protection."""
        session = SessionLocal()
        try:
            BotStateService(session, symbol=self._settings.symbol).transition("PAUSED")
            self._alerts.send("BOT_PAUSED", "bot paused by operator", context={"symbol": self._settings.symbol})
        finally:
            session.close()

    def resume(self) -> dict:
        session = SessionLocal()
        try:
            service = BotStateService(session, symbol=self._settings.symbol)
            row = service.get_or_create()
            if row.manual_resume_required:
                row = service.manual_resume()
            else:
                row = service.transition("READY")
            return {"state": row.state, "manual_resume_required": row.manual_resume_required}
        finally:
            session.close()

    def emergency_exit(self) -> dict:
        """instrucao.md #63 — force-close any open position, reconcile, then block
        new entries until an operator explicitly resumes. Never assumes success —
        confirms via reconciliation before reporting the exposure as closed."""
        session = SessionLocal()
        try:
            position_repo = PositionRepository(session)
            bot_state_service = BotStateService(session, symbol=self._settings.symbol)
            position = position_repo.get_open(self._settings.symbol)

            if position is not None:
                self._exit_position(session, bot_state_service, position_repo, position, "EMERGENCY_EXIT")

            recon = ReconciliationEngine(session, self._exchange, position_repo).reconcile(
                symbol=self._settings.symbol, base_asset=self._settings.base_asset, log_type="emergency"
            )
            bot_state_service.block_for_manual_resume(reason="emergency exit invoked", event_type="EMERGENCY_EXIT")
            row = bot_state_service.transition("EMERGENCY")

            logger.warning(
                "emergency_exit_executed",
                extra={"context": {"symbol": self._settings.symbol, "had_position": position is not None, "reconciled": recon.consistent}},
            )
            self._alerts.send(
                "EMERGENCY", "emergency exit invoked",
                context={"symbol": self._settings.symbol, "position_closed": position is not None},
            )
            return {"position_closed": position is not None, "reconciled": recon.consistent, "state": row.state}
        finally:
            session.close()

    async def run_forever(self) -> None:
        self.startup()
        listener = KlineStreamListener(
            self._settings.symbol, self._settings.entry_interval, self.handle_closed_candle
        )
        await listener.run_forever()


def _vwap(fills):
    from app.execution.fills import compute_vwap

    return compute_vwap(fills)


def _ensure_current_candle_included(candles: list, current):
    """instrucao.md #11/#99 — the exchange's REST /klines history is unreliable
    around a just-closed candle in BOTH directions: it can still lag behind (not
    yet indexed the close) OR already include the NEXT, still-forming candle as
    its last entry (real incident: REST returned open_time=22:15:00 forming
    candle last, pushing the just-closed 22:10:00 one into second-to-last, so a
    naive "fix the last element" check missed it entirely).

    `current` (from the WebSocket close event) is always authoritative for its
    own open_time — drop anything at or after it and append current instead of
    trying to reconcile positions."""
    trimmed = [c for c in candles if c.open_time < current.open_time]
    return [*trimmed, current]


async def main() -> None:
    configure_logging()
    settings = get_settings()
    worker = ExecutionWorker(settings)
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
