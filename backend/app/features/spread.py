"""Spread calculation from live best bid/ask (instrucao.md #23). Never a candle field."""
from __future__ import annotations

from decimal import Decimal

from app.exchange.types import BestBidAsk


def compute_spread(quote: BestBidAsk) -> Decimal | None:
    mid_price = (quote.bid_price + quote.ask_price) / 2
    if mid_price == 0:
        return None
    return (quote.ask_price - quote.bid_price) / mid_price
