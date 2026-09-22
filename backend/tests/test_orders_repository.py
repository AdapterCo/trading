from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.models import OrderIntentRecord, SignalRecord  # noqa: F401 — registers tables
from app.orders.client_order_id import generate_client_order_id, is_valid_client_order_id
from app.orders.repository import OrderIntentRepository, SignalRepository
from app.risk.types import RiskDecision
from app.strategy.types import Signal, SignalDecision


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _signal(decision=SignalDecision.BUY) -> Signal:
    return Signal(
        symbol="BTCUSDT",
        strategy="TrendPullbackV1",
        strategy_version="1.0.0",
        decision=decision,
        reference_price=100.2,
        candle_open_time=300_000_000,
        reasons=[] if decision == SignalDecision.BUY else ["ADX_BELOW_MINIMUM"],
        indicator_snapshot={"rsi14": 55.0, "adx14": 25.0},
    )


def test_generate_client_order_id_is_unique_and_valid():
    ids = {generate_client_order_id() for _ in range(1000)}
    assert len(ids) == 1000
    for cid in ids:
        assert is_valid_client_order_id(cid)


def test_signal_repository_persists_hold_and_buy():
    session = _session()
    repo = SignalRepository(session)

    hold_row = repo.save(_signal(SignalDecision.HOLD))
    buy_row = repo.save(_signal(SignalDecision.BUY))

    assert hold_row.decision == "HOLD"
    assert hold_row.reasons == ["ADX_BELOW_MINIMUM"]
    assert buy_row.decision == "BUY"
    assert session.query(SignalRecord).count() == 2


def test_signal_repository_roundtrips_indicator_snapshot():
    session = _session()
    repo = SignalRepository(session)
    row = repo.save(_signal())

    fetched = session.query(SignalRecord).filter_by(id=row.id).one()
    assert fetched.indicator_snapshot == {"rsi14": 55.0, "adx14": 25.0}


def test_order_intent_repository_creates_row_with_client_order_id():
    session = _session()
    signal_repo = SignalRepository(session)
    intent_repo = OrderIntentRepository(session)
    settings = Settings(_env_file=None)

    signal = _signal(SignalDecision.BUY)
    signal_repo.save(signal)

    decision = RiskDecision(
        approved=True,
        reasons=[],
        quantity=Decimal("0.001"),
        stop_price=Decimal("98.5"),
        take_profit=Decimal("103"),
        risk_amount=Decimal("10"),
    )

    intent = intent_repo.create_from_decision(signal=signal, decision=decision, settings=settings)

    assert intent.client_order_id is not None
    assert intent.status == "CREATED"
    assert intent.signal_id == signal.id
    assert intent.config_version == settings.config_version
    assert intent.strategy_version == "1.0.0"


def test_order_intent_repository_rejects_unapproved_decision():
    session = _session()
    signal_repo = SignalRepository(session)
    intent_repo = OrderIntentRepository(session)
    settings = Settings(_env_file=None)

    signal = _signal(SignalDecision.HOLD)
    signal_repo.save(signal)

    decision = RiskDecision(approved=False, reasons=["MAX_OPEN_POSITIONS_REACHED"])

    with pytest.raises(ValueError):
        intent_repo.create_from_decision(signal=signal, decision=decision, settings=settings)


def test_order_intent_lookup_by_client_order_id_supports_idempotent_retry():
    session = _session()
    signal_repo = SignalRepository(session)
    intent_repo = OrderIntentRepository(session)
    settings = Settings(_env_file=None)

    signal = _signal(SignalDecision.BUY)
    signal_repo.save(signal)
    decision = RiskDecision(
        approved=True, reasons=[], quantity=Decimal("0.001"),
        stop_price=Decimal("98.5"), take_profit=Decimal("103"), risk_amount=Decimal("10"),
    )
    created = intent_repo.create_from_decision(signal=signal, decision=decision, settings=settings)

    found = intent_repo.get_by_client_order_id(created.client_order_id)
    assert found is not None
    assert found.id == created.id

    assert intent_repo.get_by_client_order_id("does-not-exist") is None
