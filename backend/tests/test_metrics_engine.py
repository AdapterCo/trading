from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import TradeRecord
from app.metrics.engine import MetricsEngine


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add_trade(session, pnl: str, fees="0", i=0):
    now = datetime.now(timezone.utc)
    session.add(
        TradeRecord(
            position_id="pos", symbol="BTCUSDT", entry_price="100", exit_price="101",
            quantity="1", fees_total=fees, realized_pnl=pnl, exit_reason="TAKE_PROFIT",
            opened_at=now - timedelta(minutes=10 - i), closed_at=now - timedelta(minutes=9 - i),
        )
    )
    session.commit()


def test_metrics_with_no_trades_returns_none_ratios():
    engine = MetricsEngine(_session())
    snapshot = engine.compute("BTCUSDT")
    assert snapshot.trade_count == 0
    assert snapshot.win_rate is None
    assert snapshot.profit_factor is None


def test_metrics_win_rate_and_profit_factor():
    session = _session()
    _add_trade(session, "10", i=0)
    _add_trade(session, "-5", i=1)
    _add_trade(session, "20", i=2)
    _add_trade(session, "-5", i=3)

    snapshot = MetricsEngine(session).compute("BTCUSDT")
    assert snapshot.trade_count == 4
    assert snapshot.win_rate == Decimal("0.5")
    assert snapshot.gross_profit == Decimal("30")
    assert snapshot.gross_loss == Decimal("-10")
    assert snapshot.net_profit == Decimal("20")
    assert snapshot.profit_factor == Decimal("3")
    assert snapshot.expectancy == Decimal("5")


def test_metrics_consecutive_losses_counts_trailing_streak():
    session = _session()
    _add_trade(session, "10", i=0)
    _add_trade(session, "-5", i=1)
    _add_trade(session, "-5", i=2)
    _add_trade(session, "-5", i=3)

    snapshot = MetricsEngine(session).compute("BTCUSDT")
    assert snapshot.consecutive_losses == 3
    assert snapshot.consecutive_wins == 0


def test_metrics_max_drawdown_on_equity_curve():
    session = _session()
    _add_trade(session, "10", i=0)   # equity 10, peak 10
    _add_trade(session, "-8", i=1)   # equity 2, dd=8
    _add_trade(session, "-2", i=2)   # equity 0, dd=10
    _add_trade(session, "5", i=3)    # equity 5, dd still 10

    snapshot = MetricsEngine(session).compute("BTCUSDT")
    assert snapshot.max_drawdown == Decimal("10")
