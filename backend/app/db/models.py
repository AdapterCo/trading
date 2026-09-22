"""SQLAlchemy ORM models (instrucao.md #82). Grows as each phase needs new tables."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketDataCandle(Base):
    """Closed candle storage (instrucao.md #68).

    Primary key is the natural (symbol, interval, open_time) tuple — this both
    enforces the UNIQUE constraint required by #68 and lets writes be idempotent
    via a portable upsert (works identically on PostgreSQL and SQLite in tests).
    """

    __tablename__ = "market_data"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    interval: Mapped[str] = mapped_column(String(5), primary_key=True)
    open_time: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    close_time: Mapped[int] = mapped_column(BigInteger, nullable=False)

    open: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    high: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    low: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    close: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)

    volume: Mapped[str] = mapped_column(Numeric(32, 8), nullable=False)
    quote_volume: Mapped[str] = mapped_column(Numeric(32, 8), nullable=False)

    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)

    taker_buy_base_volume: Mapped[str] = mapped_column(Numeric(32, 8), nullable=False)
    taker_buy_quote_volume: Mapped[str] = mapped_column(Numeric(32, 8), nullable=False)

    source: Mapped[str] = mapped_column(String(20), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class SignalRecord(Base):
    """Every Strategy evaluation — including HOLD (instrucao.md #25, #71)."""

    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    reference_price: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    candle_open_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False)
    indicator_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class OrderIntentRecord(Base):
    """instrucao.md #42. OrderIntent existing does NOT mean an exchange order exists."""

    __tablename__ = "order_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id"), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    config_version: Mapped[str] = mapped_column(String(20), nullable=False)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)

    quantity: Mapped[str] = mapped_column(Numeric(32, 8), nullable=False)
    expected_price: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    stop_price: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    take_profit: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)
    risk_amount: Mapped[str] = mapped_column(Numeric(24, 8), nullable=False)

    client_order_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CREATED")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
