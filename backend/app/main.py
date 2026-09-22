"""FastAPI application entrypoint (instrucao.md #52 — never run the trading loop inside a request)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "api_startup",
        extra={"context": {"trading_mode": settings.trading_mode.value, "symbol": settings.symbol}},
    )
    if settings.is_live:
        logger.warning(
            "live_mode_active",
            extra={"context": {"symbol": settings.symbol}},
        )
    yield


app = FastAPI(title="AdapterTrading API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Does not touch exchange or trading state."""
    return {"status": "ok", "trading_mode": settings.trading_mode.value}
