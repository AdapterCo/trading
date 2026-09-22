"""PaperExecutionAdapter (instrucao.md #5).

TRADING_MODE=paper (and research) must NEVER send a real order — only LIVE does.
This simulates a fill against the REAL live market price (read-only, safe) so
paper trading is realistic, while guaranteeing app.exchange.*.create_order is
structurally unreachable for these modes (ExecutionWorker only constructs this
class, never the real OrderSender, when trading_mode != live).
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal

from app.core.logging import get_logger
from app.db.models import ExchangeOrderRecord, OrderIntentRecord
from app.exchange.base import ExchangeAdapter
from app.exchange.types import OrderInfo, TradeFill
from app.execution.fills import FillRepository
from app.execution.repository import ExchangeOrderRepository

logger = get_logger("execution.paper_sender")


class PaperOrderSender:
    def __init__(
        self,
        exchange: ExchangeAdapter,
        order_repo: ExchangeOrderRepository,
        fill_repo: FillRepository,
        *,
        quote_asset: str,
    ) -> None:
        self._exchange = exchange
        self._order_repo = order_repo
        self._fill_repo = fill_repo
        self._quote_asset = quote_asset

    def send(self, intent: OrderIntentRecord) -> ExchangeOrderRecord:
        already_sent = self._order_repo.get_by_client_order_id(intent.client_order_id)
        if already_sent is not None:
            return already_sent

        # Real, live, read-only market/account data — never an authenticated order endpoint.
        quote = self._exchange.get_best_bid_ask(intent.symbol)
        commission_rates = self._exchange.get_commissions(intent.symbol)
        price = quote.ask_price if intent.side == "BUY" else quote.bid_price
        quantity = Decimal(intent.quantity)
        commission = price * quantity * commission_rates.taker
        now_ms = int(time.time() * 1000)
        # exchange_order_id/exchange_trade_id columns are varchar(40) — hex (32 chars),
        # not the dashed uuid4 str() form (36 chars), keeps these comfortably under that.
        synthetic_order_id = f"PAPER-{uuid.uuid4().hex}"

        info = OrderInfo(
            exchange_order_id=synthetic_order_id,
            client_order_id=intent.client_order_id,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            status="FILLED",
            price=price,
            orig_qty=quantity,
            executed_qty=quantity,
            update_time=now_ms,
            raw={"paper": True},
        )
        row = self._order_repo.upsert_from_order_info(intent.id, info)
        intent.status = "SENT"

        fill = TradeFill(
            exchange_trade_id=f"PT-{uuid.uuid4().hex}",
            exchange_order_id=synthetic_order_id,
            symbol=intent.symbol,
            price=price,
            quantity=quantity,
            commission=commission,
            commission_asset=self._quote_asset,
            is_buyer=(intent.side == "BUY"),
            timestamp=now_ms,
        )
        self._fill_repo.upsert(row.id, fill)

        logger.info(
            "paper_order_simulated",
            extra={"context": {"client_order_id": intent.client_order_id, "price": str(price), "quantity": str(quantity)}},
        )
        return row
