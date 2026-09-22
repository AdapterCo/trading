"""MarketDataEngine (instrucao.md #10).

Orchestrates historical warmup and exposes readiness/staleness so downstream
engines (Strategy, in later phases) never consume incomplete or stale data.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.logging import get_logger
from app.exchange.base import ExchangeAdapter
from app.market_data.historical_importer import HistoricalDataImporter
from app.market_data.intervals import interval_ms
from app.market_data.repository import CandleRepository

logger = get_logger("market_data.engine")

# EMA200 needs at least 200 prior candles to initialize correctly (instrucao.md #12).
MIN_WARMUP_CANDLES = 200


@dataclass(frozen=True)
class WarmupStatus:
    symbol: str
    interval: str
    candle_count: int
    required: int

    @property
    def ready(self) -> bool:
        return self.candle_count >= self.required


class MarketDataEngine:
    def __init__(
        self,
        exchange: ExchangeAdapter,
        repository: CandleRepository,
        *,
        stale_timeout_seconds: int,
    ) -> None:
        self._exchange = exchange
        self._repository = repository
        self._stale_timeout_seconds = stale_timeout_seconds
        self._importer = HistoricalDataImporter(exchange, repository)
        self._last_received_monotonic: dict[tuple[str, str], float] = {}

    def ensure_warmup(
        self, symbol: str, interval: str, *, required: int = MIN_WARMUP_CANDLES
    ) -> WarmupStatus:
        """Backfills history until at least `required` closed candles are stored.

        Never invents candles — if the exchange returns fewer than requested
        (e.g. symbol too young), warmup simply stays incomplete (STRATEGY_READY=FALSE).
        """
        existing = self._repository.count(symbol, interval)
        if existing >= required:
            return WarmupStatus(symbol, interval, existing, required)

        step = interval_ms(interval)
        now_ms = int(time.time() * 1000)
        # Fetch enough lookback with margin for gaps/holidays in trading.
        start_time = now_ms - step * required * 2
        self._importer.import_range(symbol, interval, start_time=start_time, end_time=now_ms)

        count = self._repository.count(symbol, interval)
        return WarmupStatus(symbol, interval, count, required)

    def record_stream_heartbeat(self, symbol: str, interval: str) -> None:
        self._last_received_monotonic[(symbol, interval)] = time.monotonic()

    def is_stale(self, symbol: str, interval: str) -> bool:
        """instrucao.md #60 — no heartbeat yet counts as stale (fail safe, not fail open)."""
        last = self._last_received_monotonic.get((symbol, interval))
        if last is None:
            return True
        return (time.monotonic() - last) > self._stale_timeout_seconds
