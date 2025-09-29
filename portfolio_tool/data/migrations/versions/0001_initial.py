"""Initial schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("dt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qty", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("fees", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("exchange", sa.String(length=16)),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_index("ix_trades_dt", "trades", ["dt"])

    op.create_table(
        "lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qty_remaining", sa.Numeric(24, 8), nullable=False),
        sa.Column("cost_base_total", sa.Numeric(24, 8), nullable=False),
        sa.Column("threshold_date", sa.Date(), nullable=False),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("trades.id"), nullable=False),
    )
    op.create_index("ix_lots_symbol", "lots", ["symbol"])

    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("asof", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("ttl_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_price_cache_symbol", "price_cache", ["symbol"])
    op.create_index("ix_price_cache_asof", "price_cache", ["asof"])

    op.create_table(
        "actionables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=16)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("context", sa.Text()),
    )
    op.create_index("ix_actionables_status", "actionables", ["status"])

    op.create_table(
        "disposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sell_trade_id", sa.Integer(), sa.ForeignKey("trades.id"), nullable=False),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("lots.id"), nullable=False),
        sa.Column("qty", sa.Numeric(24, 8), nullable=False),
        sa.Column("proceeds", sa.Numeric(24, 8), nullable=False),
        sa.Column("cost_base_alloc", sa.Numeric(24, 8), nullable=False),
        sa.Column("gain_loss", sa.Numeric(24, 8), nullable=False),
        sa.Column("eligible_discount", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("entity", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("disposals")
    op.drop_index("ix_actionables_status", table_name="actionables")
    op.drop_table("actionables")
    op.drop_index("ix_price_cache_asof", table_name="price_cache")
    op.drop_index("ix_price_cache_symbol", table_name="price_cache")
    op.drop_table("price_cache")
    op.drop_index("ix_lots_symbol", table_name="lots")
    op.drop_table("lots")
    op.drop_index("ix_trades_dt", table_name="trades")
    op.drop_index("ix_trades_symbol", table_name="trades")
    op.drop_table("trades")
