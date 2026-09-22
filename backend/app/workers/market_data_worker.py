"""worker-market-data (instrucao.md #66) — runs 24/7 independently of Strategy/execution.

Backfills history for BASE_INTERVAL, then keeps streaming closed candles live,
persisting every one and tracking a heartbeat for staleness/observability (#86).
"""
from __future__ import annotations

import asyncio
import time

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import SessionLocal
from app.exchange.binance_adapter import BinanceExchangeAdapter
from app.market_data.engine import MarketDataEngine
from app.market_data.repository import CandleRepository
from app.market_data.stream import KlineStreamListener

logger = get_logger("worker.market_data")


async def main() -> None:
    configure_logging()
    settings = get_settings()
    exchange = BinanceExchangeAdapter(settings)

    session = SessionLocal()
    repository = CandleRepository(session)
    engine = MarketDataEngine(
        exchange, repository, stale_timeout_seconds=settings.stale_market_data_timeout_seconds
    )

    logger.info("market_data_worker_starting", extra={"context": {"symbol": settings.symbol}})
    status = engine.ensure_warmup(settings.symbol, settings.base_interval)
    logger.info(
        "market_data_warmup_status",
        extra={
            "context": {
                "symbol": settings.symbol,
                "interval": settings.base_interval,
                "candle_count": status.candle_count,
                "required": status.required,
                "ready": status.ready,
            }
        },
    )

    def on_closed_candle(candle) -> None:
        repository.upsert(candle, source="binance_ws")
        session.commit()
        engine.record_stream_heartbeat(settings.symbol, settings.base_interval)
        logger.info(
            "candle_closed",
            extra={"context": {"symbol": candle.symbol, "interval": candle.interval, "open_time": candle.open_time}},
        )

    listener = KlineStreamListener(settings.symbol, settings.base_interval, on_closed_candle)

    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(30)
            stale = engine.is_stale(settings.symbol, settings.base_interval)
            logger.info(
                "market_data_worker_heartbeat",
                extra={"context": {"last_heartbeat": time.time(), "stale": stale}},
            )

    await asyncio.gather(listener.run_forever(), heartbeat_loop())


if __name__ == "__main__":
    asyncio.run(main())
