"""AlertService (instrucao.md #90).

A failure in this service must never break financial protection — every send is
wrapped so an alert-delivery problem can't crash or block the caller (worker-execution).
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("alerts")

# instrucao.md #90 — the canonical event types this service must be able to raise.
EVENT_TYPES = {
    "BOT_BLOCKED", "BOT_PAUSED", "EMERGENCY",
    "ORDER_REJECTED", "ORDER_ERROR",
    "RECONCILIATION_ERROR",
    "MARKET_DATA_LOST", "USER_STREAM_LOST",
    "DATABASE_ERROR",
    "DAILY_LOSS_LIMIT", "DRAWDOWN_LIMIT", "CONSECUTIVE_LOSS_LIMIT",
}


class AlertService:
    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url

    def send(self, event_type: str, message: str, *, context: dict | None = None) -> None:
        if event_type not in EVENT_TYPES:
            logger.warning("alert_unknown_event_type", extra={"context": {"event_type": event_type}})

        try:
            logger.warning(
                "alert_raised",
                extra={"context": {"event_type": event_type, "message": message, **(context or {})}},
            )
            if self._webhook_url:
                self._send_webhook(event_type, message, context or {})
        except Exception:  # noqa: BLE001 — instrucao.md #90: never let alerting break the caller
            logger.exception("alert_service_delivery_failed", extra={"context": {"event_type": event_type}})

    def _send_webhook(self, event_type: str, message: str, context: dict) -> None:
        import httpx

        httpx.post(
            self._webhook_url,
            json={"event_type": event_type, "message": message, "context": context},
            timeout=5.0,
        )
