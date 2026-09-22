"""Central application configuration (instrucao.md #94 — no magic numbers scattered in code)."""
from __future__ import annotations

from decimal import getcontext
from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# instrucao.md #8 — Decimal precision must be configured explicitly.
getcontext().prec = 28


class TradingMode(str, Enum):
    RESEARCH = "research"
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application / trading mode (instrucao.md #5) ---
    # Default is PAPER, never LIVE. LIVE requires explicit operator configuration.
    trading_mode: TradingMode = TradingMode.PAPER
    environment: str = "development"

    # --- Config version (instrucao.md #84) — bump manually whenever a risk/strategy
    # parameter below changes, so every OrderIntent can point at what produced it. ---
    config_version: str = "1"

    # --- Database (instrucao.md #6, #82) ---
    database_url: str = "postgresql+psycopg://trading:trading@localhost:5432/adaptertrading"

    # --- Symbol / market (instrucao.md #3) ---
    symbol: str = "BTCUSDT"
    base_asset: str = "BTC"
    quote_asset: str = "USDT"

    # --- Timeframes (instrucao.md #9) ---
    base_interval: str = "1m"
    entry_interval: str = "5m"
    trend_interval: str = "15m"
    macro_interval: str = "1h"

    # --- Strategy thresholds (instrucao.md #13-#23) ---
    adx_min: int = 20
    rsi_entry_min: int = 45
    rsi_entry_max: int = 65
    pullback_max_distance: float = 0.003
    min_volume_ratio: float = 1.0
    min_taker_buy_ratio: float = 0.50
    max_spread: float = 0.001

    # --- Risk (instrucao.md #26-#40) ---
    risk_per_trade: float = 0.01
    max_capital_allocation: float = 0.95
    max_daily_loss: float = 0.03
    max_drawdown: float = 0.10
    max_consecutive_losses: int = 3

    stop_atr_multiplier: float = 1.5
    max_stop_percent: float = 0.02

    take_profit_r: float = 2.0
    break_even_trigger_r: float = 1.0
    trailing_start_r: float = 1.5
    trailing_atr_multiplier: float = 1.0

    cooldown_candles: int = 2
    max_open_positions: int = 1

    max_orders_per_hour: int = 6
    max_entries_per_day: int = 10

    # --- Market data health (instrucao.md #60) ---
    stale_market_data_timeout_seconds: int = 90

    # --- Exchange credentials (instrucao.md #92 — never logged, never in Git) ---
    binance_api_key: str | None = Field(default=None, repr=False)
    binance_api_secret: str | None = Field(default=None, repr=False)

    # --- Auth for critical endpoints (instrucao.md #93, #64) ---
    control_api_token: str | None = Field(default=None, repr=False)

    @property
    def is_live(self) -> bool:
        return self.trading_mode is TradingMode.LIVE


@lru_cache
def get_settings() -> Settings:
    return Settings()
