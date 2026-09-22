from decimal import Decimal

import pytest

from app.exchange.types import Candle
from app.market_data.historical_importer import (
    Gap,
    detect_gaps,
    drop_unclosed_candles,
    validate_no_duplicates,
    validate_ordering,
)


def _candle(open_time: int, interval: str = "1m") -> Candle:
    return Candle(
        symbol="BTCUSDT",
        interval=interval,
        open_time=open_time,
        close_time=open_time + 59_999,
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("10"),
        quote_volume=Decimal("1000"),
        trade_count=5,
        taker_buy_base_volume=Decimal("5"),
        taker_buy_quote_volume=Decimal("500"),
    )


def test_validate_ordering_accepts_ascending():
    candles = [_candle(0), _candle(60_000), _candle(120_000)]
    validate_ordering(candles)  # no raise


def test_validate_ordering_rejects_out_of_order():
    candles = [_candle(60_000), _candle(0)]
    with pytest.raises(ValueError):
        validate_ordering(candles)


def test_validate_no_duplicates_rejects_repeated_open_time():
    candles = [_candle(0), _candle(0)]
    with pytest.raises(ValueError):
        validate_no_duplicates(candles)


def test_detect_gaps_finds_missing_candles():
    candles = [_candle(0), _candle(60_000), _candle(240_000)]  # missing 120_000 and 180_000
    gaps = detect_gaps(candles, "1m")
    assert gaps == [Gap(after_open_time=60_000, before_open_time=240_000, missing_candles=2)]


def test_detect_gaps_empty_when_contiguous():
    candles = [_candle(0), _candle(60_000), _candle(120_000)]
    assert detect_gaps(candles, "1m") == []


def test_drop_unclosed_candles_removes_still_forming_last_candle():
    # candle at open_time=60_000 has close_time=119_999; "now" is mid-interval.
    candles = [_candle(0), _candle(60_000)]
    result = drop_unclosed_candles(candles, now_ms=100_000)
    assert [c.open_time for c in result] == [0]


def test_drop_unclosed_candles_keeps_fully_elapsed_candles():
    candles = [_candle(0), _candle(60_000)]
    result = drop_unclosed_candles(candles, now_ms=200_000)
    assert [c.open_time for c in result] == [0, 60_000]
