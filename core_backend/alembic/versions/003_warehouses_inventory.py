"""003 warehouses + inventory — almacenes, zonas, saldos, ledger, transacciones

Revision ID: 003
Revises: 002
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── warehouses (RLS por tenant_id) ────────────────────────────────────
    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("location_address", sa.String(255), nullable=True),
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="'UTC'"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_warehouses_tenant_code", "warehouses", ["tenant_id", "code"], unique=True)
    op.create_index("idx_warehouses_tenant_active", "warehouses", ["tenant_id", "is_active"])

    op.execute("ALTER TABLE warehouses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE warehouses FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON warehouses "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── zones (RLS por tenant_id) ─────────────────────────────────────────
    op.create_table(
        "zones",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_zone_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("zones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("zone_type", sa.String(20), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("capacity_volume", sa.Numeric(18, 4), nullable=True),
        sa.Column("capacity_weight", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_zones_warehouse_code", "zones", ["warehouse_id", "code"], unique=True)
    op.create_index("idx_zones_tenant", "zones", ["tenant_id"])
    op.create_index("idx_zones_warehouse", "zones", ["warehouse_id"])

    op.execute("ALTER TABLE zones ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE zones FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON zones "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── transactions (cabecera de cada operación del motor) ───────────────
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(100), nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'COMPLETED'"),
        sa.Column("items_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.String(255), nullable=True),
    )
    op.create_index("idx_transactions_tenant_type", "transactions", ["tenant_id", "transaction_type"])
    op.create_index("idx_transactions_tenant_date", "transactions", ["tenant_id", sa.text("created_at DESC")])
    op.create_index("idx_transactions_reference", "transactions", ["tenant_id", "reference_type", "reference_id"])

    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transactions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON transactions "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── stock_balances (saldo por producto/zona/lote con OCC) ─────────────
    op.create_table(
        "stock_balances",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=True),
        sa.Column("physical_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("reserved_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("available_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Unique: un balance por (tenant, producto, zona, lote). NULL lot usa 'N/A' en el índice.
    op.execute(
        "CREATE UNIQUE INDEX idx_stock_product_zone_lot "
        "ON stock_balances(tenant_id, product_id, zone_id, COALESCE(lot_number, 'N/A'))"
    )
    op.create_index("idx_stock_tenant_product", "stock_balances", ["tenant_id", "product_id"])
    op.create_index("idx_stock_tenant_warehouse", "stock_balances", ["tenant_id", "warehouse_id"])

    op.execute("ALTER TABLE stock_balances ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stock_balances FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON stock_balances "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── inventory_ledger (append-only, inmutable) ─────────────────────────
    op.create_table(
        "inventory_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("qty_change", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("lot_number", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(100), nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_ledger_product_date", "inventory_ledger", ["tenant_id", "product_id", sa.text("created_at DESC")])
    op.create_index("idx_ledger_transaction", "inventory_ledger", ["tenant_id", "transaction_id"])
    op.create_index("idx_ledger_warehouse_date", "inventory_ledger", ["tenant_id", "warehouse_id", sa.text("created_at DESC")])

    op.execute("ALTER TABLE inventory_ledger ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE inventory_ledger FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON inventory_ledger "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON inventory_ledger")
    op.drop_table("inventory_ledger")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON stock_balances")
    op.drop_table("stock_balances")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON transactions")
    op.drop_table("transactions")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON zones")
    op.drop_table("zones")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON warehouses")
    op.drop_table("warehouses")
