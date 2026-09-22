"""HistoricalDataImporter (instrucao.md #67).

Source of truth is always the exchange's official REST API. Validates ordering,
duplicates and gaps. Never fabricates missing candles (instrucao.md #12, #67).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.logging import get_logger
from app.exchange.base import ExchangeAdapter
from app.exchange.types import Candle
from app.market_data.intervals import interval_ms
from app.market_data.repository import CandleRepository

logger = get_logger("market_data.importer")


@dataclass(frozen=True)
class Gap:
    after_open_time: int
    before_open_time: int
    missing_candles: int


class HistoricalDataImporter:
    def __init__(self, exchange: ExchangeAdapter, repository: CandleRepository) -> None:
        self._exchange = exchange
        self._repository = repository

    def import_range(
        self, symbol: str, interval: str, *, start_time: int, end_time: int | None = None, page_limit: int = 1000
    ) -> list[Gap]:
        """Fetches [start_time, end_time) in pages, validates, persists. Returns detected gaps."""
        all_candles: list[Candle] = []
        cursor = start_time
        while True:
            page = self._exchange.get_klines(
                symbol, interval, start_time=cursor, end_time=end_time, limit=page_limit
            )
            if not page:
                break
            all_candles.extend(page)
            last_open_time = page[-1].open_time
            if len(page) < page_limit:
                break
            next_cursor = last_open_time + interval_ms(interval)
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if end_time is not None and cursor >= end_time:
                break

        all_candles = drop_unclosed_candles(all_candles)
        validate_ordering(all_candles)
        validate_no_duplicates(all_candles)
        gaps = detect_gaps(all_candles, interval)

        if gaps:
            logger.warning(
                "market_data_gaps_detected",
                extra={"context": {"symbol": symbol, "interval": interval, "gap_count": len(gaps)}},
            )

        self._repository.upsert_many(all_candles, source="binance_rest_historical")
        return gaps


def drop_unclosed_candles(candles: list[Candle], *, now_ms: int | None = None) -> list[Candle]:
    """REST /klines can return the still-forming current candle as its last row.

    instrucao.md #11 forbids treating an open candle as closed, so anything whose
    close_time has not yet elapsed is dropped rather than stored.
    """
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    return [c for c in candles if c.close_time < now]


def validate_ordering(candles: list[Candle]) -> None:
    for prev, curr in zip(candles, candles[1:]):
        if curr.open_time <= prev.open_time:
            raise ValueError(
                f"candles out of order: {prev.open_time} followed by {curr.open_time}"
            )


def validate_no_duplicates(candles: list[Candle]) -> None:
    seen = set()
    for c in candles:
        if c.open_time in seen:
            raise ValueError(f"duplicate candle open_time: {c.open_time}")
        seen.add(c.open_time)


def detect_gaps(candles: list[Candle], interval: str) -> list[Gap]:
    step = interval_ms(interval)
    gaps: list[Gap] = []
    for prev, curr in zip(candles, candles[1:]):
        expected_next = prev.open_time + step
        if curr.open_time > expected_next:
            missing = (curr.open_time - expected_next) // step
            gaps.append(
                Gap(after_open_time=prev.open_time, before_open_time=curr.open_time, missing_candles=int(missing))
            )
    return gaps
