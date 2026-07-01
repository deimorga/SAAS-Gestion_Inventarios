"""013 product sale_price — agregar precio de venta al producto

Revision ID: 013
Revises: 012
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("sale_price", sa.Numeric(18, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "sale_price")
