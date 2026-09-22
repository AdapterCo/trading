"""client_order_id generation (instrucao.md #45).

Must be unique per order and persisted BEFORE the order is sent (idempotency).
Kept short and alphanumeric-only to stay safely within exchange newClientOrderId
constraints — the exact current limit must still be re-checked against the
official API docs when Fase 8 wires this into a real create_order call (#53).
"""
from __future__ import annotations

import uuid

PREFIX = "AT"  # AdapterTrading


def generate_client_order_id() -> str:
    return f"{PREFIX}{uuid.uuid4().hex}"


def is_valid_client_order_id(value: str) -> bool:
    return bool(value) and value.isalnum() and len(value) <= 36
