from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import BotStateRecord, RiskEventRecord  # noqa: F401
from app.safety.state import BotStateService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_get_or_create_starts_in_starting_state():
    service = BotStateService(_session(), symbol="BTCUSDT")
    row = service.get_or_create()
    assert row.state == "STARTING"
    assert Decimal(row.high_water_mark) == Decimal("0")


def test_transition_rejects_invalid_state():
    service = BotStateService(_session(), symbol="BTCUSDT")
    try:
        service.transition("NOT_A_REAL_STATE")
        assert False, "should have raised"
    except ValueError:
        pass


def test_update_equity_raises_high_water_mark_but_never_lowers_it():
    service = BotStateService(_session(), symbol="BTCUSDT")
    service.update_equity(Decimal("100"))
    service.update_equity(Decimal("120"))
    service.update_equity(Decimal("90"))  # a drawdown must not lower the HWM
    row = service.get_or_create()
    assert Decimal(row.high_water_mark) == Decimal("120")


def test_consecutive_losses_increments_on_loss_and_resets_on_win():
    service = BotStateService(_session(), symbol="BTCUSDT")
    service.record_trade_result(Decimal("-5"))
    service.record_trade_result(Decimal("-3"))
    row = service.record_trade_result(Decimal("2"))
    assert row.consecutive_losses == 0

    service.record_trade_result(Decimal("-1"))
    row = service.record_trade_result(Decimal("-1"))
    assert row.consecutive_losses == 2


def test_block_for_manual_resume_requires_explicit_resume():
    service = BotStateService(_session(), symbol="BTCUSDT")
    row = service.block_for_manual_resume(reason="3 consecutive losses", event_type="CONSECUTIVE_LOSS_LIMIT")
    assert row.manual_resume_required is True
    assert row.state == "BLOCKED"

    resumed = service.manual_resume()
    assert resumed.manual_resume_required is False
    assert resumed.state == "READY"
