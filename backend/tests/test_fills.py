from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import ExchangeOrderRecord, FillRecord, OrderIntentRecord, SignalRecord  # noqa: F401
from app.exchange.types import OrderInfo, TradeFill
from app.execution.fills import (
    FillRepository,
    compute_vwap,
    extract_fills_from_order_info,
    total_commission_in_asset,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _fill(**overrides) -> TradeFill:
    base = dict(
        exchange_trade_id="1", exchange_order_id="99", symbol="BTCUSDT",
        price=Decimal("100"), quantity=Decimal("1"),
        commission=Decimal("0.001"), commission_asset="BNB",
        is_buyer=True, timestamp=1_700_000_000_000,
    )
    base.update(overrides)
    return TradeFill(**base)


def _exchange_order_row(session) -> ExchangeOrderRecord:
    row = ExchangeOrderRecord(
        order_intent_id="intent-1", exchange_order_id="99", client_order_id="AT-1",
        symbol="BTCUSDT", side="BUY", order_type="MARKET", status="FILLED",
        price="100", orig_qty="1", executed_qty="1",
    )
    session.add(row)
    session.commit()
    return row


def test_compute_vwap_weighted_by_quantity():
    fills = [_fill(price=Decimal("100"), quantity=Decimal("1")), _fill(price=Decimal("110"), quantity=Decimal("3"))]
    avg, qty = compute_vwap(fills)
    assert avg == Decimal("107.5")  # (100*1+110*3)/4
    assert qty == Decimal("4")


def test_compute_vwap_empty_never_invents_a_price():
    avg, qty = compute_vwap([])
    assert avg == Decimal("0")
    assert qty == Decimal("0")


def test_total_commission_filters_by_asset():
    fills = [
        _fill(commission=Decimal("0.001"), commission_asset="BNB"),
        _fill(commission=Decimal("0.5"), commission_asset="USDT"),
    ]
    assert total_commission_in_asset(fills, "BNB") == Decimal("0.001")
    assert total_commission_in_asset(fills, "USDT") == Decimal("0.5")


def test_fill_repository_upsert_is_idempotent_by_trade_id():
    session = _session()
    order_row = _exchange_order_row(session)
    repo = FillRepository(session)

    repo.upsert(order_row.id, _fill(exchange_trade_id="777"))
    repo.upsert(order_row.id, _fill(exchange_trade_id="777"))  # duplicate call

    assert session.query(FillRecord).count() == 1


def test_extract_fills_from_order_info_maps_raw_fills():
    info = OrderInfo(
        exchange_order_id="99", client_order_id="AT-1", symbol="BTCUSDT",
        side="BUY", order_type="MARKET", status="FILLED",
        price=Decimal("0"), orig_qty=Decimal("1"), executed_qty=Decimal("1"),
        update_time=1_700_000_000_000,
        raw={"fills": [{"price": "100", "qty": "1", "commission": "0.001", "commissionAsset": "BNB", "tradeId": 5}]},
    )
    fills = extract_fills_from_order_info(info)
    assert len(fills) == 1
    assert fills[0].exchange_trade_id == "5"
    assert fills[0].price == Decimal("100")
    assert fills[0].is_buyer is True


def test_extract_fills_from_order_info_empty_when_no_fills_key():
    info = OrderInfo(
        exchange_order_id="99", client_order_id="AT-1", symbol="BTCUSDT",
        side="BUY", order_type="MARKET", status="NEW",
        price=Decimal("0"), orig_qty=Decimal("1"), executed_qty=Decimal("0"),
        update_time=1_700_000_000_000, raw={},
    )
    assert extract_fills_from_order_info(info) == []
