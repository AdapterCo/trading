"""Safe order sending (instrucao.md #46 — the core idempotency rule).

SEND -> TIMEOUT -> QUERY client_order_id -> EXISTS? YES: RECONCILE / NO: SAFE RETRY.

Never duplicates an order via retry. Never assumes a network failure means the
order wasn't placed — always verifies against the exchange first (instrucao.md #116).
"""
from __future__ import annotations

from decimal import Decimal

from binance_common.errors import NetworkError, NotFoundError, ServerError, TooManyRequestsError

from app.core.logging import get_logger
from app.db.models import ExchangeOrderRecord, OrderIntentRecord
from app.exchange.base import ExchangeAdapter
from app.execution.fills import FillRepository, extract_fills_from_order_info
from app.execution.repository import ExchangeOrderRepository

logger = get_logger("execution.sender")

# Errors where the request may or may not have reached the matching engine —
# the only safe move is to ask the exchange, never to guess.
UNCERTAIN_OUTCOME_ERRORS = (NetworkError, ServerError, TooManyRequestsError)


class OrderSendError(Exception):
    """Raised when the outcome could not be determined even after querying (instrucao.md #46)."""


class OrderSender:
    def __init__(
        self,
        exchange: ExchangeAdapter,
        order_repo: ExchangeOrderRepository,
        fill_repo: FillRepository | None = None,
    ) -> None:
        self._exchange = exchange
        self._order_repo = order_repo
        self._fill_repo = fill_repo

    def send(self, intent: OrderIntentRecord) -> ExchangeOrderRecord:
        """Idempotent: safe to call more than once for the same OrderIntent."""
        already_sent = self._order_repo.get_by_client_order_id(intent.client_order_id)
        if already_sent is not None:
            logger.info(
                "order_already_sent_skipping",
                extra={"context": {"client_order_id": intent.client_order_id}},
            )
            return already_sent

        return self._attempt_send(intent, allow_retry=True)

    def _attempt_send(self, intent: OrderIntentRecord, *, allow_retry: bool) -> ExchangeOrderRecord:
        try:
            info = self._exchange.create_order(
                symbol=intent.symbol,
                side=intent.side,
                order_type=intent.order_type,
                quantity=_decimal(intent.quantity),
                client_order_id=intent.client_order_id,
            )
            row = self._order_repo.upsert_from_order_info(intent.id, info)
            intent.status = "SENT"
            self._persist_fills(row.id, info)
            return row
        except UNCERTAIN_OUTCOME_ERRORS:
            logger.warning(
                "order_send_uncertain_reconciling",
                extra={"context": {"client_order_id": intent.client_order_id}},
            )
            return self._reconcile_after_uncertain_send(intent, allow_retry=allow_retry)

    def _reconcile_after_uncertain_send(self, intent: OrderIntentRecord, *, allow_retry: bool) -> ExchangeOrderRecord:
        """instrucao.md #46 — query by client_order_id before ever retrying."""
        try:
            info = self._exchange.get_order(intent.symbol, client_order_id=intent.client_order_id)
        except NotFoundError:
            # Confirmed: the exchange never received/created this order — safe to retry
            # exactly once, using the SAME client_order_id (still idempotent).
            if not allow_retry:
                intent.status = "UNKNOWN_BLOCKED"
                raise OrderSendError(
                    f"order still not found after retry for client_order_id={intent.client_order_id}"
                ) from None
            logger.info(
                "order_confirmed_not_placed_retrying",
                extra={"context": {"client_order_id": intent.client_order_id}},
            )
            return self._attempt_send(intent, allow_retry=False)
        except Exception as exc:  # noqa: BLE001 — query itself failed; block, never assume
            intent.status = "UNKNOWN_BLOCKED"
            raise OrderSendError(
                f"could not determine outcome for client_order_id={intent.client_order_id}: {exc}"
            ) from exc

        # The order exists on the exchange — reconcile, do not send again.
        row = self._order_repo.upsert_from_order_info(intent.id, info)
        intent.status = "SENT"
        self._persist_fills(row.id, info)
        return row

    def _persist_fills(self, exchange_order_record_id: str, info) -> None:
        if self._fill_repo is None:
            return
        for fill in extract_fills_from_order_info(info):
            self._fill_repo.upsert(exchange_order_record_id, fill)


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))
