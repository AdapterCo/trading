"""Persistence for closed candles (instrucao.md #68). Idempotent writes only."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import MarketDataCandle
from app.exchange.types import Candle


class CandleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, candle: Candle, *, source: str) -> None:
        """Insert or update a candle by its natural key (symbol, interval, open_time).

        Uses session.merge, which is portable across PostgreSQL (production) and
        SQLite (tests) since the primary key is the natural composite key — no
        dialect-specific ON CONFLICT clause needed.
        """
        row = MarketDataCandle(
            symbol=candle.symbol,
            interval=candle.interval,
            open_time=candle.open_time,
            close_time=candle.close_time,
            open=str(candle.open),
            high=str(candle.high),
            low=str(candle.low),
            close=str(candle.close),
            volume=str(candle.volume),
            quote_volume=str(candle.quote_volume),
            trade_count=candle.trade_count,
            taker_buy_base_volume=str(candle.taker_buy_base_volume),
            taker_buy_quote_volume=str(candle.taker_buy_quote_volume),
            source=source,
            received_at=datetime.now(timezone.utc),
        )
        self._session.merge(row)

    def upsert_many(self, candles: list[Candle], *, source: str) -> None:
        for candle in candles:
            self.upsert(candle, source=source)
        self._session.commit()

    def count(self, symbol: str, interval: str) -> int:
        return (
            self._session.query(MarketDataCandle)
            .filter_by(symbol=symbol, interval=interval)
            .count()
        )

    def latest_open_time(self, symbol: str, interval: str) -> int | None:
        row = (
            self._session.query(MarketDataCandle)
            .filter_by(symbol=symbol, interval=interval)
            .order_by(MarketDataCandle.open_time.desc())
            .first()
        )
        return row.open_time if row else None

    def get_recent(self, symbol: str, interval: str, limit: int) -> list[MarketDataCandle]:
        rows = (
            self._session.query(MarketDataCandle)
            .filter_by(symbol=symbol, interval=interval)
            .order_by(MarketDataCandle.open_time.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))
