"""create market_data table

Revision ID: 0001
Revises:
Create Date: 2026-09-22

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_data",
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("interval", sa.String(length=5), primary_key=True),
        sa.Column("open_time", sa.BigInteger(), primary_key=True),
        sa.Column("close_time", sa.BigInteger(), nullable=False),
        sa.Column("open", sa.Numeric(24, 8), nullable=False),
        sa.Column("high", sa.Numeric(24, 8), nullable=False),
        sa.Column("low", sa.Numeric(24, 8), nullable=False),
        sa.Column("close", sa.Numeric(24, 8), nullable=False),
        sa.Column("volume", sa.Numeric(32, 8), nullable=False),
        sa.Column("quote_volume", sa.Numeric(32, 8), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("taker_buy_base_volume", sa.Numeric(32, 8), nullable=False),
        sa.Column("taker_buy_quote_volume", sa.Numeric(32, 8), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_data")
