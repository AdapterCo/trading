from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import LedgerEntryRecord  # noqa: F401
from app.exchange.types import TradeFill
from app.ledger.service import LedgerService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _fill(price="100", qty="1", commission="0.1", commission_asset="USDT") -> TradeFill:
    return TradeFill(
        exchange_trade_id="1", exchange_order_id="1", symbol="BTCUSDT",
        price=Decimal(price), quantity=Decimal(qty),
        commission=Decimal(commission), commission_asset=commission_asset,
        is_buyer=True, timestamp=1_700_000_000_000,
    )


def test_record_buy_fill_creates_negative_cash_entry_and_fee():
    session = _session()
    ledger = LedgerService(session, quote_asset="USDT")

    ledger.record_fill(symbol="BTCUSDT", side="BUY", fill=_fill(), position_id="pos-1")

    entries = ledger.entries_for_symbol("BTCUSDT")
    assert len(entries) == 2
    buy_entry = next(e for e in entries if e.event_type == "BUY")
    fee_entry = next(e for e in entries if e.event_type == "FEE")
    assert Decimal(buy_entry.amount) == Decimal("-100")
    assert Decimal(fee_entry.amount) == Decimal("-0.1")


def test_record_sell_fill_creates_positive_cash_entry():
    session = _session()
    ledger = LedgerService(session, quote_asset="USDT")

    ledger.record_fill(symbol="BTCUSDT", side="SELL", fill=_fill(price="110", commission="0"), position_id="pos-1")

    entries = ledger.entries_for_symbol("BTCUSDT")
    assert len(entries) == 1  # no fee entry when commission is zero
    assert entries[0].event_type == "SELL"
    assert Decimal(entries[0].amount) == Decimal("110")


def test_record_realized_pnl():
    session = _session()
    ledger = LedgerService(session, quote_asset="USDT")

    ledger.record_realized_pnl(symbol="BTCUSDT", position_id="pos-1", realized_pnl=Decimal("8.5"))

    entries = ledger.entries_for_symbol("BTCUSDT")
    assert entries[0].event_type == "REALIZED_PNL"
    assert Decimal(entries[0].amount) == Decimal("8.5")


def test_record_adjustment_never_touches_original_entries():
    session = _session()
    ledger = LedgerService(session, quote_asset="USDT")

    ledger.record_fill(symbol="BTCUSDT", side="BUY", fill=_fill(commission="0"), position_id="pos-1")
    original_count = len(ledger.entries_for_symbol("BTCUSDT"))

    ledger.record_adjustment(symbol="BTCUSDT", asset="USDT", amount=Decimal("-1"), note="correcting a fee misattribution")

    entries = ledger.entries_for_symbol("BTCUSDT")
    assert len(entries) == original_count + 1  # appended, nothing removed/edited
    assert entries[-1].event_type == "ADJUSTMENT"


def test_ledger_service_exposes_no_update_or_delete_methods():
    # Immutability guarantee at the application layer (instrucao.md #54).
    public_methods = {name for name in dir(LedgerService) if not name.startswith("_")}
    assert not any(m in public_methods for m in ("update", "delete", "edit", "remove"))
