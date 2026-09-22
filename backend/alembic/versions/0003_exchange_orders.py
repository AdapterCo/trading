"""create exchange_orders table

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-22

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exchange_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_intent_id", sa.String(length=36), sa.ForeignKey("order_intents.id"), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=40), nullable=False),
        sa.Column("client_order_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("orig_qty", sa.Numeric(32, 8), nullable=False),
        sa.Column("executed_qty", sa.Numeric(32, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("exchange_orders")
