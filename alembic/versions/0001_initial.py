"""initial tables

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

currency = sa.Enum("RUB", "USD", "EUR", name="currency_enum")
status = sa.Enum("PENDING", "SUCCEEDED", "FAILED", name="payment_status_enum")


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("webhook_url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_payments_idempotency_key", "payments", ["idempotency_key"], unique=True)
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outbox_status", "outbox", ["status"])


def downgrade():
    op.drop_table("outbox")
    op.drop_table("payments")
    status.drop(op.get_bind(), checkfirst=True)
    currency.drop(op.get_bind(), checkfirst=True)
