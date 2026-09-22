from decimal import Decimal
from types import SimpleNamespace

from app.market_data.stream import KlineStreamListener


def _kline_event(x: bool):
    k = SimpleNamespace(
        t=1_700_000_000_000, T=1_700_000_059_999, s="BTCUSDT", i="1m",
        o="100.00", h="101.00", l="99.00", c="100.50",
        v="10.0", n=5, x=x, q="1000.0", V="5.0", Q="500.0",
    )
    return SimpleNamespace(k=k)


def test_open_candle_is_ignored():
    received = []
    listener = KlineStreamListener("BTCUSDT", "1m", lambda c: received.append(c))
    listener._handle_message(_kline_event(x=False))
    assert received == []


def test_closed_candle_is_forwarded_as_decimal_candle():
    received = []
    listener = KlineStreamListener("BTCUSDT", "1m", lambda c: received.append(c))
    listener._handle_message(_kline_event(x=True))

    assert len(received) == 1
    candle = received[0]
    assert candle.symbol == "BTCUSDT"
    assert candle.open == Decimal("100.00")
    assert candle.close == Decimal("100.50")
    assert isinstance(candle.volume, Decimal)


def test_heartbeat_updated_on_message():
    listener = KlineStreamListener("BTCUSDT", "1m", lambda c: None)
    assert listener.last_message_at is None
    listener._handle_message(_kline_event(x=False))
    assert listener.last_message_at is not None
