"""create signals and order_intents tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-22

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("strategy", sa.String(length=50), nullable=False),
        sa.Column("strategy_version", sa.String(length=20), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("reference_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("candle_open_time", sa.BigInteger(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("indicator_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "order_intents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("signal_id", sa.String(length=36), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("strategy_version", sa.String(length=20), nullable=False),
        sa.Column("config_version", sa.String(length=20), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(32, 8), nullable=False),
        sa.Column("expected_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("stop_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("take_profit", sa.Numeric(24, 8), nullable=False),
        sa.Column("risk_amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("client_order_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("order_intents")
    op.drop_table("signals")
