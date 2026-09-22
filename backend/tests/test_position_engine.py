from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import PositionRecord, TradeRecord  # noqa: F401
from app.exchange.types import TradeFill
from app.positions.engine import PositionEngine
from app.positions.repository import PositionRepository


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _fill(price, qty, commission="0", commission_asset="USDT", trade_id="1") -> TradeFill:
    return TradeFill(
        exchange_trade_id=trade_id, exchange_order_id="1", symbol="BTCUSDT",
        price=Decimal(price), quantity=Decimal(qty),
        commission=Decimal(commission), commission_asset=commission_asset,
        is_buyer=True, timestamp=1_700_000_000_000,
    )


def test_open_from_fills_computes_vwap_entry_and_fees():
    session = _session()
    engine = PositionEngine(PositionRepository(session))

    fills = [_fill("100", "1", "0.1", trade_id="1"), _fill("110", "3", "0.3", trade_id="2")]
    position = engine.open_from_fills(
        symbol="BTCUSDT", fills=fills, stop_price=Decimal("95"), take_profit=Decimal("120"), fee_asset="USDT",
    )

    assert Decimal(position.quantity) == Decimal("4")
    assert Decimal(position.average_entry) == Decimal("107.5")
    assert Decimal(position.fees_total) == Decimal("0.4")
    assert position.status == "OPEN"
    assert Decimal(position.initial_stop_price) == Decimal("95")


def test_open_from_fills_rejects_zero_quantity():
    session = _session()
    engine = PositionEngine(PositionRepository(session))
    try:
        engine.open_from_fills(symbol="BTCUSDT", fills=[], stop_price=Decimal("95"), take_profit=Decimal("120"), fee_asset="USDT")
        assert False, "should have raised"
    except ValueError:
        pass


def test_unrealized_pnl_accounts_for_fees():
    session = _session()
    engine = PositionEngine(PositionRepository(session))
    position = engine.open_from_fills(
        symbol="BTCUSDT", fills=[_fill("100", "1", "1")], stop_price=Decimal("95"), take_profit=Decimal("120"), fee_asset="USDT",
    )
    pnl = engine.unrealized_pnl(position, Decimal("110"))
    assert pnl == Decimal("9")  # (110-100)*1 - 1 fee


def test_close_position_computes_realized_pnl_and_creates_trade():
    session = _session()
    repo = PositionRepository(session)
    engine = PositionEngine(repo)
    position = engine.open_from_fills(
        symbol="BTCUSDT", fills=[_fill("100", "1", "1")], stop_price=Decimal("95"), take_profit=Decimal("120"), fee_asset="USDT",
    )

    trade = repo.close(position, exit_price=Decimal("110"), exit_fees=Decimal("1"), exit_reason="TAKE_PROFIT")

    assert position.status == "CLOSED"
    assert Decimal(trade.realized_pnl) == Decimal("8")  # (110-100)*1 - (1+1) fees
    assert trade.exit_reason == "TAKE_PROFIT"
    assert session.query(TradeRecord).count() == 1
