"""Unit tests for BinanceExchangeAdapter mapping logic (instrucao.md #95, #106).

No network calls — the underlying SDK client is monkeypatched with fakes that
mimic the real binance-sdk-spot response shapes verified by introspection.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.exchange.binance_adapter import BinanceExchangeAdapter


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        binance_api_key="test-key",
        binance_api_secret="test-secret",
    )


def _wrap(data):
    return SimpleNamespace(data=lambda: data)


@pytest.fixture
def adapter():
    return BinanceExchangeAdapter(_settings())


def test_get_server_time(adapter):
    adapter._client.rest_api.time = lambda: _wrap(SimpleNamespace(server_time=1_700_000_000_000))
    assert adapter.get_server_time() == 1_700_000_000_000


def test_get_account_maps_balances_to_decimal(adapter):
    account = SimpleNamespace(
        can_trade=True,
        can_withdraw=False,
        can_deposit=True,
        update_time=123,
        balances=[
            SimpleNamespace(asset="USDT", free="100.50000000", locked="0.00000000"),
            SimpleNamespace(asset="BTC", free="0.00100000", locked="0.00000000"),
        ],
    )
    adapter._client.rest_api.get_account = lambda: _wrap(account)

    result = adapter.get_account()
    assert result.can_withdraw is False
    assert result.balances[0].free == Decimal("100.50000000")
    assert isinstance(result.balances[0].free, Decimal)


def test_get_symbol_info_parses_filters(adapter):
    price_filter = SimpleNamespace(filter_type="PRICE_FILTER", tick_size="0.01000000")
    lot_size = SimpleNamespace(filter_type="LOT_SIZE", step_size="0.00001000", min_qty="0.00001000", max_qty="9000.00000000")
    notional = SimpleNamespace(filter_type="NOTIONAL", min_notional="5.00000000", max_notional=None)

    symbol_info = SimpleNamespace(
        symbol="BTCUSDT",
        status="TRADING",
        base_asset="BTC",
        quote_asset="USDT",
        is_spot_trading_allowed=True,
        filters=[
            SimpleNamespace(actual_instance=price_filter),
            SimpleNamespace(actual_instance=lot_size),
            SimpleNamespace(actual_instance=notional),
        ],
    )
    exchange_info = SimpleNamespace(symbols=[symbol_info])
    adapter._client.rest_api.exchange_info = lambda symbol: _wrap(exchange_info)

    rules = adapter.get_symbol_info("BTCUSDT")
    assert rules.tick_size == Decimal("0.01000000")
    assert rules.step_size == Decimal("0.00001000")
    assert rules.min_notional == Decimal("5.00000000")
    assert rules.max_notional is None

    # second call must hit the cache, not the exchange again
    adapter._client.rest_api.exchange_info = lambda symbol: (_ for _ in ()).throw(AssertionError("should be cached"))
    assert adapter.get_symbol_info("BTCUSDT") is rules


def test_get_best_bid_ask(adapter):
    ticker = SimpleNamespace(symbol="BTCUSDT", bid_price="60000.00", bid_qty="0.5", ask_price="60001.00", ask_qty="0.4")
    adapter._client.rest_api.ticker_book_ticker = lambda symbol: _wrap(SimpleNamespace(actual_instance=ticker))

    result = adapter.get_best_bid_ask("BTCUSDT")
    assert result.bid_price == Decimal("60000.00")
    assert result.ask_price == Decimal("60001.00")


def test_get_trades_maps_commission_and_side(adapter):
    trade = SimpleNamespace(
        id=1, order_id=99, symbol="BTCUSDT", price="60000.00", qty="0.001",
        commission="0.00000010", commission_asset="BTC", is_buyer=True, time=1_700_000_000_000,
    )
    adapter._client.rest_api.my_trades = lambda symbol, limit: _wrap([trade])

    fills = adapter.get_trades("BTCUSDT")
    assert len(fills) == 1
    assert fills[0].commission_asset == "BTC"
    assert fills[0].is_buyer is True


def test_create_order_not_implemented_in_fase_2(adapter):
    with pytest.raises(NotImplementedError):
        adapter.create_order(symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity=Decimal("1"), client_order_id="x")


def test_cancel_order_not_implemented_in_fase_2(adapter):
    with pytest.raises(NotImplementedError):
        adapter.cancel_order("BTCUSDT", client_order_id="x")
