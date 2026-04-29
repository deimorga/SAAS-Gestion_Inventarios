"""009 batches_serials — lotes y numeros de serie

Revision ID: 009
Revises: 008
Create Date: 2026-04-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── batches ───────────────────────────────────────────────────────────────
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=False),
        sa.Column("manufactured_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("initial_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_batches_product", "batches", ["product_id"])
    op.create_index("idx_batches_expiry", "batches", ["tenant_id", "expiry_date"])
    op.create_unique_constraint("uq_batches_tenant_product_number", "batches", ["tenant_id", "product_id", "batch_number"])

    op.execute("ALTER TABLE batches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE batches FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON batches "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── serial_numbers ────────────────────────────────────────────────────────
    op.create_table(
        "serial_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("batches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("serial_number", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="AVAILABLE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_serial_numbers_product", "serial_numbers", ["product_id"])
    op.create_index("idx_serial_numbers_status", "serial_numbers", ["tenant_id", "status"])
    op.create_unique_constraint("uq_serial_numbers_tenant_sn", "serial_numbers", ["tenant_id", "serial_number"])

    op.execute("ALTER TABLE serial_numbers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE serial_numbers FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON serial_numbers "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON serial_numbers")
    op.drop_table("serial_numbers")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON batches")
    op.drop_table("batches")
