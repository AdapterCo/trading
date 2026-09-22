"""Exchange-agnostic value objects returned by ExchangeAdapter (instrucao.md #53, #43).

All financial fields use Decimal — never float (instrucao.md #8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class AccountBalance:
    asset: str
    free: Decimal
    locked: Decimal


@dataclass(frozen=True)
class AccountInfo:
    can_trade: bool
    can_withdraw: bool
    can_deposit: bool
    balances: list[AccountBalance]
    update_time: int


@dataclass(frozen=True)
class SymbolRules:
    """Exchange-imposed rules for a symbol. Never hardcode these (instrucao.md #43)."""

    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    min_notional: Decimal | None
    max_notional: Decimal | None
    is_spot_trading_allowed: bool


@dataclass(frozen=True)
class CommissionRates:
    symbol: str
    maker: Decimal
    taker: Decimal


@dataclass(frozen=True)
class BestBidAsk:
    symbol: str
    bid_price: Decimal
    bid_qty: Decimal
    ask_price: Decimal
    ask_qty: Decimal


@dataclass(frozen=True)
class OrderInfo:
    exchange_order_id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    price: Decimal
    orig_qty: Decimal
    executed_qty: Decimal
    update_time: int
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Candle:
    """Raw candle as returned by the exchange REST/WebSocket API (instrucao.md #68)."""

    symbol: str
    interval: str
    open_time: int
    close_time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal
    trade_count: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal


@dataclass(frozen=True)
class TradeFill:
    exchange_trade_id: str
    exchange_order_id: str
    symbol: str
    price: Decimal
    quantity: Decimal
    commission: Decimal
    commission_asset: str
    is_buyer: bool
    timestamp: int
