"""008 suppliers — directorio de proveedores y costos de reposicion

Revision ID: 008
Revises: 007
Create Date: 2026-04-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── suppliers ─────────────────────────────────────────────────────────────
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tax_id", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MXN"),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_suppliers_tenant", "suppliers", ["tenant_id", "is_active"])
    op.create_unique_constraint("uq_suppliers_tenant_code", "suppliers", ["tenant_id", "code"])

    op.execute("ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE suppliers FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON suppliers "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── supplier_products ─────────────────────────────────────────────────────
    op.create_table(
        "supplier_products",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_sku", sa.String(100), nullable=True),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MXN"),
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("moq", sa.Numeric(18, 4), nullable=False, server_default="1"),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_supplier_products_supplier", "supplier_products", ["supplier_id"])
    op.create_index("idx_supplier_products_product", "supplier_products", ["product_id"])
    op.create_unique_constraint("uq_supplier_products", "supplier_products", ["supplier_id", "product_id"])

    op.execute("ALTER TABLE supplier_products ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE supplier_products FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON supplier_products "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON supplier_products")
    op.drop_table("supplier_products")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON suppliers")
    op.drop_table("suppliers")
