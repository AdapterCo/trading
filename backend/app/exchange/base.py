"""ExchangeAdapter interface (instrucao.md #53).

StrategyEngine and RiskEngine must never import a concrete exchange SDK directly —
only this interface. Order-sending methods are intentionally NotImplementedError
in Fase 2; they are implemented with idempotency/retry safety in Fase 8 (instrucao.md #46).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from app.exchange.types import (
    AccountInfo,
    BestBidAsk,
    Candle,
    CommissionRates,
    OrderInfo,
    SymbolRules,
    TradeFill,
)


class ExchangeAdapter(ABC):
    @abstractmethod
    def get_server_time(self) -> int:
        """Exchange server time in milliseconds since epoch."""

    @abstractmethod
    def get_account(self) -> AccountInfo:
        ...

    @abstractmethod
    def get_balances(self) -> list:
        ...

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolRules:
        ...

    @abstractmethod
    def get_commissions(self, symbol: str) -> CommissionRates:
        ...

    @abstractmethod
    def get_best_bid_ask(self, symbol: str) -> BestBidAsk:
        ...

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        interval: str,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[Candle]:
        """Historical candles (instrucao.md #10, #67). Never fabricates missing data."""

    @abstractmethod
    def get_open_orders(self, symbol: str) -> list[OrderInfo]:
        ...

    @abstractmethod
    def get_order(self, symbol: str, *, client_order_id: str | None = None, exchange_order_id: str | None = None) -> OrderInfo:
        ...

    @abstractmethod
    def get_recent_orders(self, symbol: str, limit: int = 50) -> list[OrderInfo]:
        ...

    @abstractmethod
    def get_trades(self, symbol: str, limit: int = 50) -> list[TradeFill]:
        ...

    @abstractmethod
    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        client_order_id: str,
        price: Decimal | None = None,
    ) -> OrderInfo:
        """Implemented in Fase 8 with client_order_id idempotency (instrucao.md #45, #46)."""

    @abstractmethod
    def cancel_order(self, symbol: str, *, client_order_id: str | None = None, exchange_order_id: str | None = None) -> OrderInfo:
        """Implemented in Fase 8."""
