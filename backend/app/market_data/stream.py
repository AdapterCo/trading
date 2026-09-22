"""Live candle WebSocket stream (instrucao.md #10, #11).

Wraps binance-sdk-spot's public kline stream. Emits Candle only for CLOSED
candles (k.x == True) — open candles are never handed to the strategy layer.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal

from binance_common.configuration import ConfigurationWebSocketStreams
from binance_common.constants import SPOT_WS_STREAMS_PROD_URL

from app.core.logging import get_logger
from app.exchange.types import Candle

logger = get_logger("market_data.stream")

OnClosedCandle = Callable[[Candle], Awaitable[None] | None]


class KlineStreamListener:
    """Reconnecting listener for a single symbol/interval kline stream (instrucao.md #65)."""

    def __init__(self, symbol: str, interval: str, on_closed_candle: OnClosedCandle) -> None:
        self._symbol = symbol
        self._interval = interval
        self._on_closed_candle = on_closed_candle
        self._stop = False
        self.last_message_at: float | None = None

    def stop(self) -> None:
        self._stop = True

    async def run_forever(self, *, backoff_seconds: float = 5.0) -> None:
        while not self._stop:
            try:
                await self._run_once()
            except Exception:  # noqa: BLE001 — reconnect loop must never die silently
                logger.exception(
                    "market_data_stream_disconnected",
                    extra={"context": {"symbol": self._symbol, "interval": self._interval}},
                )
            if self._stop:
                return
            await asyncio.sleep(backoff_seconds)

    async def _run_once(self) -> None:
        from binance_sdk_spot.spot import Spot  # local import keeps SDK optional for unit tests

        config = ConfigurationWebSocketStreams(stream_url=SPOT_WS_STREAMS_PROD_URL)
        client = Spot(config_ws_streams=config)
        connection = await client.websocket_streams.create_connection()
        try:
            stream = await connection.kline(symbol=self._symbol.lower(), interval=self._interval)
            stream.on("message", self._handle_message)
            while not self._stop:
                await asyncio.sleep(1)
        finally:
            await connection.close_connection(close_session=True)

    def _handle_message(self, data) -> None:
        import time

        self.last_message_at = time.monotonic()
        k = data.k
        if not k.x:
            return  # candle still open — instrucao.md #11
        candle = Candle(
            symbol=k.s,
            interval=k.i,
            open_time=int(k.t),
            close_time=int(k.T),
            open=Decimal(str(k.o)),
            high=Decimal(str(k.h)),
            low=Decimal(str(k.l)),
            close=Decimal(str(k.c)),
            volume=Decimal(str(k.v)),
            quote_volume=Decimal(str(k.q)),
            trade_count=int(k.n),
            taker_buy_base_volume=Decimal(str(k.V)),
            taker_buy_quote_volume=Decimal(str(k.Q)),
        )
        result = self._on_closed_candle(candle)
        if asyncio.iscoroutine(result):
            asyncio.ensure_future(result)
