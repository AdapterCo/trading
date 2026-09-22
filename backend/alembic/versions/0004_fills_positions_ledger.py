"""create fills, positions, ledger_entries, trades, reconciliation_log, risk_events

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("exchange_order_record_id", sa.String(length=36), sa.ForeignKey("exchange_orders.id"), nullable=False),
        sa.Column("exchange_trade_id", sa.String(length=40), nullable=False, unique=True),
        sa.Column("exchange_order_id", sa.String(length=40), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(32, 8), nullable=False),
        sa.Column("commission", sa.Numeric(24, 8), nullable=False),
        sa.Column("commission_asset", sa.String(length=10), nullable=False),
        sa.Column("is_buyer", sa.Boolean(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(32, 8), nullable=False),
        sa.Column("average_entry", sa.Numeric(24, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(24, 8), nullable=False),
        sa.Column("fees_total", sa.Numeric(24, 8), nullable=False),
        sa.Column("initial_stop_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("stop_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(24, 8), nullable=True),
        sa.Column("trailing_stop", sa.Numeric(24, 8), nullable=True),
        sa.Column("break_even_active", sa.Boolean(), nullable=False),
        sa.Column("highest_price_since_entry", sa.Numeric(24, 8), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(24, 8), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("asset", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("position_id", sa.String(length=36), sa.ForeignKey("positions.id"), nullable=True),
        sa.Column("reference_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("position_id", sa.String(length=36), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("entry_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("exit_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(32, 8), nullable=False),
        sa.Column("fees_total", sa.Numeric(24, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(24, 8), nullable=False),
        sa.Column("exit_reason", sa.String(length=30), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "reconciliation_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("internal_state", sa.JSON(), nullable=False),
        sa.Column("exchange_state", sa.JSON(), nullable=False),
        sa.Column("difference", sa.JSON(), nullable=False),
        sa.Column("resolution", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "bot_state",
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("high_water_mark", sa.Numeric(24, 8), nullable=False),
        sa.Column("daily_reference_equity", sa.Numeric(24, 8), nullable=False),
        sa.Column("daily_reference_date", sa.String(length=10), nullable=False),
        sa.Column("consecutive_losses", sa.Integer(), nullable=False),
        sa.Column("manual_resume_required", sa.Boolean(), nullable=False),
        sa.Column("block_reason", sa.String(length=100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "risk_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("manual_resume_required", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("risk_events")
    op.drop_table("bot_state")
    op.drop_table("reconciliation_log")
    op.drop_table("trades")
    op.drop_table("ledger_entries")
    op.drop_table("positions")
    op.drop_table("fills")
