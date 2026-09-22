"""OrderSender safe-retry / idempotency tests (instrucao.md #46, #95)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from binance_common.errors import BadRequestError, NetworkError, NotFoundError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import ExchangeOrderRecord, OrderIntentRecord, SignalRecord  # noqa: F401
from app.exchange.types import OrderInfo
from app.execution.repository import ExchangeOrderRepository
from app.execution.sender import OrderSendError, OrderSender


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _intent(**overrides) -> OrderIntentRecord:
    base = dict(
        id="intent-1", signal_id="signal-1", strategy_version="1.0.0", config_version="1",
        symbol="BTCUSDT", side="BUY", order_type="MARKET",
        quantity="0.00100000", expected_price="100.00000000", stop_price="98.50000000",
        take_profit="103.00000000", risk_amount="1.00000000",
        client_order_id="AT-TEST-1", status="CREATED",
    )
    base.update(overrides)
    return OrderIntentRecord(**base)


def _order_info(**overrides) -> OrderInfo:
    base = dict(
        exchange_order_id="555", client_order_id="AT-TEST-1", symbol="BTCUSDT",
        side="BUY", order_type="MARKET", status="FILLED",
        price=Decimal("100"), orig_qty=Decimal("0.001"), executed_qty=Decimal("0.001"),
        update_time=1_700_000_000_000,
    )
    base.update(overrides)
    return OrderInfo(**base)


class FakeExchange:
    def __init__(self, create_order_side_effect, get_order_side_effect=None):
        self._create_order_effect = create_order_side_effect
        self._get_order_effect = get_order_side_effect
        self.create_order_calls = 0
        self.get_order_calls = 0

    def create_order(self, **kwargs):
        self.create_order_calls += 1
        result = self._create_order_effect(self.create_order_calls)
        if isinstance(result, Exception):
            raise result
        return result

    def get_order(self, symbol, *, client_order_id=None, exchange_order_id=None):
        self.get_order_calls += 1
        result = self._get_order_effect(self.get_order_calls)
        if isinstance(result, Exception):
            raise result
        return result


def test_successful_send_persists_and_marks_intent_sent():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(create_order_side_effect=lambda n: _order_info())
    sender = OrderSender(exchange, repo)

    intent = _intent()
    row = sender.send(intent)

    assert row.status == "FILLED"
    assert intent.status == "SENT"
    assert exchange.create_order_calls == 1


def test_second_send_call_is_a_noop_idempotent():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(create_order_side_effect=lambda n: _order_info())
    sender = OrderSender(exchange, repo)

    intent = _intent()
    sender.send(intent)
    sender.send(intent)  # second call, e.g. worker restarted

    assert exchange.create_order_calls == 1  # never resent


def test_network_error_then_order_found_reconciles_without_resending():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(
        create_order_side_effect=lambda n: NetworkError("timeout"),
        get_order_side_effect=lambda n: _order_info(status="NEW"),
    )
    sender = OrderSender(exchange, repo)

    row = sender.send(_intent())

    assert row.status == "NEW"
    assert exchange.create_order_calls == 1  # never called twice
    assert exchange.get_order_calls == 1


def test_network_error_then_not_found_retries_once_and_succeeds():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(
        create_order_side_effect=lambda n: NetworkError("timeout") if n == 1 else _order_info(),
        get_order_side_effect=lambda n: NotFoundError("no such order"),
    )
    sender = OrderSender(exchange, repo)

    row = sender.send(_intent())

    assert row.status == "FILLED"
    assert exchange.create_order_calls == 2  # original attempt + one safe retry
    assert exchange.get_order_calls == 1


def test_network_error_twice_in_a_row_blocks_without_infinite_retry():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(
        create_order_side_effect=lambda n: NetworkError("timeout"),
        get_order_side_effect=lambda n: NotFoundError("no such order"),
    )
    sender = OrderSender(exchange, repo)

    with pytest.raises(OrderSendError):
        sender.send(_intent())

    assert exchange.create_order_calls == 2  # exactly one retry, never unbounded


def test_query_failure_during_reconcile_blocks_as_unknown():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(
        create_order_side_effect=lambda n: NetworkError("timeout"),
        get_order_side_effect=lambda n: NetworkError("query also failed"),
    )
    sender = OrderSender(exchange, repo)

    intent = _intent()
    with pytest.raises(OrderSendError):
        sender.send(intent)
    assert intent.status == "UNKNOWN_BLOCKED"


def test_client_rejection_is_not_retried():
    session = _session()
    repo = ExchangeOrderRepository(session)
    exchange = FakeExchange(create_order_side_effect=lambda n: BadRequestError("insufficient balance"))
    sender = OrderSender(exchange, repo)

    with pytest.raises(BadRequestError):
        sender.send(_intent())

    assert exchange.create_order_calls == 1  # a clear rejection must never trigger a retry
