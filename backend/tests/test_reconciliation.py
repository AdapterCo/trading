from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import PositionRecord, ReconciliationLogRecord  # noqa: F401
from app.exchange.types import AccountBalance, AccountInfo
from app.positions.repository import PositionRepository
from app.reconciliation.engine import ReconciliationEngine


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class FakeExchange:
    def __init__(self, btc_balance: Decimal):
        self._btc_balance = btc_balance

    def get_account(self):
        return AccountInfo(
            can_trade=True, can_withdraw=False, can_deposit=True, update_time=1,
            balances=[AccountBalance(asset="BTC", free=self._btc_balance, locked=Decimal("0"))],
        )


def test_reconciliation_consistent_when_balance_matches_open_position():
    session = _session()
    position_repo = PositionRepository(session)
    position_repo.create(
        symbol="BTCUSDT", quantity=Decimal("0.001"), average_entry=Decimal("100"),
        cost_basis=Decimal("0.1"), fees_total=Decimal("0"), stop_price=Decimal("95"), take_profit=Decimal("110"),
    )

    engine = ReconciliationEngine(session, FakeExchange(Decimal("0.001")), position_repo)
    result = engine.reconcile(symbol="BTCUSDT", base_asset="BTC")

    assert result.consistent is True
    assert session.query(ReconciliationLogRecord).count() == 1
    assert session.query(ReconciliationLogRecord).first().status == "CONSISTENT"


def test_reconciliation_blocked_when_balance_diverges():
    session = _session()
    position_repo = PositionRepository(session)
    position_repo.create(
        symbol="BTCUSDT", quantity=Decimal("0.001"), average_entry=Decimal("100"),
        cost_basis=Decimal("0.1"), fees_total=Decimal("0"), stop_price=Decimal("95"), take_profit=Decimal("110"),
    )

    # exchange reports far less BTC than the DB thinks is open — e.g. an external withdrawal or missed fill
    engine = ReconciliationEngine(session, FakeExchange(Decimal("0.0002")), position_repo)
    result = engine.reconcile(symbol="BTCUSDT", base_asset="BTC")

    assert result.consistent is False
    assert session.query(ReconciliationLogRecord).first().status == "BLOCKED"


def test_reconciliation_consistent_with_no_open_position_and_zero_balance():
    session = _session()
    position_repo = PositionRepository(session)

    engine = ReconciliationEngine(session, FakeExchange(Decimal("0")), position_repo)
    result = engine.reconcile(symbol="BTCUSDT", base_asset="BTC")

    assert result.consistent is True


def test_reconciliation_tolerates_dust_within_threshold():
    session = _session()
    position_repo = PositionRepository(session)
    position_repo.create(
        symbol="BTCUSDT", quantity=Decimal("0.00100000"), average_entry=Decimal("100"),
        cost_basis=Decimal("0.1"), fees_total=Decimal("0"), stop_price=Decimal("95"), take_profit=Decimal("110"),
    )
    # tiny rounding residue well under the dust tolerance
    engine = ReconciliationEngine(session, FakeExchange(Decimal("0.00100005")), position_repo)
    result = engine.reconcile(symbol="BTCUSDT", base_asset="BTC")

    assert result.consistent is True
