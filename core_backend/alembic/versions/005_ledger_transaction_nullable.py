"""inventory_ledger.transaction_id nullable for reservation confirmations

Revision ID: 005
Revises: 004
Create Date: 2026-04-28

Reservation confirmations write ledger ISSUE entries that are not backed by
a row in the transactions table, so transaction_id must allow NULL.
"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("inventory_ledger", "transaction_id", nullable=True)


def downgrade() -> None:
    op.alter_column("inventory_ledger", "transaction_id", nullable=False)
