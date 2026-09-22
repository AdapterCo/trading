"""Integration test for ExecutionWorker wiring (instrucao.md Fase 14).

Strategy's own decision logic is already exhaustively tested in test_trend_pullback_v1.py,
so here a fake Strategy is injected to isolate the RiskEngine -> OrderIntent ->
OrderSender -> PositionEngine -> Ledger -> BotState chain, which is what Fase 14 adds.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db import models  # noqa: F401 — registers all tables
from app.db.base import Base
from app.db.models import BotStateRecord, LedgerEntryRecord, PositionRecord
from app.exchange.types import (
    AccountBalance,
    AccountInfo,
    BestBidAsk,
    Candle,
    OrderInfo,
    SymbolRules,
)
from app.risk.types import RiskDecision
from app.strategy.types import Signal, SignalDecision
from app.workers.execution_worker import ExecutionWorker


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _candle(open_time: int, close: str) -> Candle:
    c = Decimal(close)
    return Candle(
        symbol="BTCUSDT", interval="5m", open_time=open_time, close_time=open_time + 299_999,
        open=c, high=c + Decimal("0.1"), low=c - Decimal("0.1"), close=c,  # small nonzero range -> small nonzero ATR
        volume=Decimal("10"), quote_volume=Decimal("1000"), trade_count=5,
        taker_buy_base_volume=Decimal("5"), taker_buy_quote_volume=Decimal("600"),
    )


class FakeExchange:
    def __init__(self, *, usdt_balance: Decimal, ask_price: Decimal, btc_balance: Decimal = Decimal("0")):
        self.usdt_balance = usdt_balance
        self.btc_balance = btc_balance
        self.ask_price = ask_price
        self.create_order_calls = []

    def get_account(self):
        return AccountInfo(
            can_trade=True, can_withdraw=False, can_deposit=True, update_time=1,
            balances=[
                AccountBalance(asset="USDT", free=self.usdt_balance, locked=Decimal("0")),
                AccountBalance(asset="BTC", free=self.btc_balance, locked=Decimal("0")),
            ],
        )

    def get_klines(self, symbol, interval, *, start_time=None, end_time=None, limit=1000):
        return [_candle(i * 300_000, "100") for i in range(30)]

    def get_symbol_info(self, symbol):
        return SymbolRules(
            symbol="BTCUSDT", status="TRADING", base_asset="BTC", quote_asset="USDT",
            tick_size=Decimal("0.01"), step_size=Decimal("0.00001"),
            min_qty=Decimal("0.00001"), max_qty=Decimal("9000"),
            min_notional=Decimal("5"), max_notional=None, is_spot_trading_allowed=True,
        )

    def get_best_bid_ask(self, symbol):
        return BestBidAsk(symbol="BTCUSDT", bid_price=self.ask_price, bid_qty=Decimal("1"), ask_price=self.ask_price, ask_qty=Decimal("1"))

    def create_order(self, **kwargs):
        self.create_order_calls.append(kwargs)
        qty = kwargs["quantity"]
        return OrderInfo(
            exchange_order_id="1", client_order_id=kwargs["client_order_id"], symbol="BTCUSDT",
            side=kwargs["side"], order_type=kwargs["order_type"], status="FILLED",
            price=Decimal("0"), orig_qty=qty, executed_qty=qty, update_time=1_700_000_000_000,
            raw={"fills": [{"price": str(self.ask_price), "qty": str(qty), "commission": "0", "commissionAsset": "USDT", "tradeId": 1}]},
        )

    def get_order(self, symbol, *, client_order_id=None, exchange_order_id=None):
        qty = Decimal("0.001")
        return OrderInfo(
            exchange_order_id="1", client_order_id=client_order_id, symbol=symbol,
            side="BUY", order_type="MARKET", status="FILLED",
            price=Decimal("0"), orig_qty=qty, executed_qty=qty, update_time=1_700_000_000_000,
            raw={"fills": [{"price": str(self.ask_price), "qty": str(qty), "commission": "0", "commissionAsset": "USDT", "tradeId": 1}]},
        )


class FixedBuySignalStrategy:
    name = "FixedTest"
    version = "1.0.0"

    def on_candle(self, candle_open_time, context):
        return Signal(
            symbol="BTCUSDT", strategy=self.name, strategy_version=self.version,
            decision=SignalDecision.BUY, reference_price=100.0, candle_open_time=candle_open_time,
            reasons=[], indicator_snapshot={"atr14": 1.0},
        )


def _worker(exchange, settings=None) -> ExecutionWorker:
    worker = ExecutionWorker(settings or Settings(_env_file=None), exchange=exchange)
    worker._strategy = FixedBuySignalStrategy()
    worker._last_reconciliation_ok = True
    return worker


def test_run_cycle_opens_position_on_approved_buy(monkeypatch):
    session = _session()
    monkeypatch.setattr("app.workers.execution_worker.SessionLocal", lambda: session)

    exchange = FakeExchange(usdt_balance=Decimal("1000"), ask_price=Decimal("100"))
    worker = _worker(exchange)

    candle = _candle(300_000_000, "100")
    worker._run_cycle(session, candle)

    positions = session.query(PositionRecord).all()
    assert len(positions) == 1
    assert positions[0].status == "OPEN"
    assert len(exchange.create_order_calls) == 1
    assert exchange.create_order_calls[0]["side"] == "BUY"

    ledger_entries = session.query(LedgerEntryRecord).all()
    assert any(e.event_type == "BUY" for e in ledger_entries)


def test_run_cycle_does_not_trade_with_insufficient_balance():
    session = _session()
    exchange = FakeExchange(usdt_balance=Decimal("0"), ask_price=Decimal("100"))
    worker = _worker(exchange)

    candle = _candle(300_000_000, "100")
    worker._run_cycle(session, candle)

    assert session.query(PositionRecord).count() == 0
    assert len(exchange.create_order_calls) == 0


def test_run_cycle_skips_entry_when_manual_resume_required():
    session = _session()
    exchange = FakeExchange(usdt_balance=Decimal("1000"), ask_price=Decimal("100"))
    worker = _worker(exchange)

    from app.safety.state import BotStateService

    BotStateService(session, symbol="BTCUSDT").block_for_manual_resume(reason="test", event_type="TEST")

    candle = _candle(300_000_000, "100")
    worker._run_cycle(session, candle)

    assert len(exchange.create_order_calls) == 0
    assert session.query(PositionRecord).count() == 0


def test_run_cycle_skips_entry_when_paused_but_would_still_protect_position(monkeypatch):
    session = _session()
    monkeypatch.setattr("app.workers.execution_worker.SessionLocal", lambda: session)
    exchange = FakeExchange(usdt_balance=Decimal("1000"), ask_price=Decimal("100"))
    worker = _worker(exchange)

    from app.safety.state import BotStateService

    BotStateService(session, symbol="BTCUSDT").transition("PAUSED")

    candle = _candle(300_000_000, "100")
    worker._run_cycle(session, candle)

    # no position existed, so nothing to protect — but a new entry must still be blocked while PAUSED
    assert len(exchange.create_order_calls) == 0
    assert session.query(PositionRecord).count() == 0


def test_pause_then_resume_round_trip(monkeypatch):
    session = _session()
    monkeypatch.setattr("app.workers.execution_worker.SessionLocal", lambda: session)
    worker = _worker(FakeExchange(usdt_balance=Decimal("1000"), ask_price=Decimal("100")))

    worker.pause()
    row = session.get(BotStateRecord, "BTCUSDT")
    assert row.state == "PAUSED"

    result = worker.resume()
    assert result["state"] == "READY"
    assert result["manual_resume_required"] is False


def test_emergency_exit_closes_open_position_and_blocks_new_entries(monkeypatch):
    session = _session()
    monkeypatch.setattr("app.workers.execution_worker.SessionLocal", lambda: session)
    exchange = FakeExchange(usdt_balance=Decimal("1000"), ask_price=Decimal("100"), btc_balance=Decimal("0.001"))
    worker = _worker(exchange)

    from app.positions.repository import PositionRepository

    PositionRepository(session).create(
        symbol="BTCUSDT", quantity=Decimal("0.001"), average_entry=Decimal("100"),
        cost_basis=Decimal("0.1"), fees_total=Decimal("0"), stop_price=Decimal("95"), take_profit=Decimal("110"),
    )

    result = worker.emergency_exit()

    assert result["position_closed"] is True
    assert result["state"] == "EMERGENCY"
    assert session.query(PositionRecord).filter_by(status="OPEN").count() == 0
    row = session.get(BotStateRecord, "BTCUSDT")
    assert row.manual_resume_required is True

    # new entries must stay blocked even if a later cycle would otherwise approve one
    candle = _candle(300_600_000, "100")
    worker._run_cycle(session, candle)
    assert len(exchange.create_order_calls) == 1  # only the emergency SELL, no new BUY afterward
