"""002 catalog — categories, products, product_uom, kit_components + RLS

Revision ID: 002
Revises: 001
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── categories (RLS por tenant_id) ────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("path", sa.String(1000), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_categories_tenant_id", "categories", ["tenant_id"])
    op.create_index("idx_categories_tenant_parent", "categories", ["tenant_id", "parent_id"])
    op.create_index("idx_categories_tenant_path", "categories", ["tenant_id", "path"])
    op.create_index("idx_categories_tenant_parent_name", "categories", ["tenant_id", "parent_id", "name"], unique=True)

    op.execute("ALTER TABLE categories ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE categories FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON categories "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── products (RLS por tenant_id) ──────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sku", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_uom", sa.String(20), nullable=False),
        sa.Column("current_cpp", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("reorder_point", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("track_serials", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("track_lots", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("track_expiry", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_kit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("low_stock_alert_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_products_tenant_sku", "products", ["tenant_id", "sku"], unique=True)
    op.create_index("idx_products_tenant_active", "products", ["tenant_id", "is_active"])
    op.create_index("idx_products_tenant_category", "products", ["tenant_id", "category_id"])

    op.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE products FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON products "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── product_uom (sin RLS directo — filtrado vía product) ──────────────
    op.create_table(
        "product_uom",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uom_code", sa.String(20), nullable=False),
        sa.Column("conversion_factor", sa.Numeric(18, 6), nullable=False),
        sa.Column("is_purchase_uom", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_sale_uom", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("idx_product_uom_product_code", "product_uom", ["product_id", "uom_code"])
    op.create_index("idx_product_uom_product", "product_uom", ["product_id"])

    op.execute("ALTER TABLE product_uom ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE product_uom FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON product_uom "
        "USING (EXISTS ("
        "  SELECT 1 FROM products p "
        "  WHERE p.id = product_uom.product_id "
        "  AND p.tenant_id::text = current_setting('app.current_tenant', true)"
        "))"
    )

    # ── kit_components (sin RLS directo — filtrado vía product) ───────────
    op.create_table(
        "kit_components",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("kit_product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
    )
    op.create_index("idx_kit_components_kit", "kit_components", ["kit_product_id"])
    op.create_index("idx_kit_components_component", "kit_components", ["component_product_id"])

    op.execute("ALTER TABLE kit_components ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE kit_components FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON kit_components "
        "USING (EXISTS ("
        "  SELECT 1 FROM products p "
        "  WHERE p.id = kit_components.kit_product_id "
        "  AND p.tenant_id::text = current_setting('app.current_tenant', true)"
        "))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON kit_components")
    op.drop_table("kit_components")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON product_uom")
    op.drop_table("product_uom")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON products")
    op.drop_table("products")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON categories")
    op.drop_table("categories")
