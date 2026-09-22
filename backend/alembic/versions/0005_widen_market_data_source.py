"""widen market_data.source and order_type columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22

Two varchar widths too narrow for real values — only caught against the real
Postgres on the VPS, since SQLite (used in local tests) never enforces length:
- market_data.source: "binance_rest_historical" is 23 chars, was varchar(20).
- order_intents/exchange_orders.order_type: not yet triggered in practice
  (only "MARKET" sent so far), but "STOP_LOSS_LIMIT"/"TAKE_PROFIT_LIMIT" are
  15/18 chars and the adapter already supports LIMIT orders — widened now
  instead of waiting for the same failure mode later.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "market_data", "source",
        existing_type=sa.String(length=20), type_=sa.String(length=30), existing_nullable=False,
    )
    op.alter_column(
        "order_intents", "order_type",
        existing_type=sa.String(length=10), type_=sa.String(length=20), existing_nullable=False,
    )
    op.alter_column(
        "exchange_orders", "order_type",
        existing_type=sa.String(length=10), type_=sa.String(length=20), existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "exchange_orders", "order_type",
        existing_type=sa.String(length=20), type_=sa.String(length=10), existing_nullable=False,
    )
    op.alter_column(
        "order_intents", "order_type",
        existing_type=sa.String(length=20), type_=sa.String(length=10), existing_nullable=False,
    )
    op.alter_column(
        "market_data", "source",
        existing_type=sa.String(length=30), type_=sa.String(length=20), existing_nullable=False,
    )
