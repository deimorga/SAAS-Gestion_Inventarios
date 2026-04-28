"""004 reservations + valuation_snapshots — reservas de stock y snapshots contables

Revision ID: 004
Revises: 003
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── reservations ──────────────────────────────────────────────────────────
    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'ACTIVE'"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_reservations_tenant_status_exp", "reservations", ["tenant_id", "status", "expires_at"])
    op.execute("ALTER TABLE reservations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reservations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON reservations "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── reservation_items ─────────────────────────────────────────────────────
    op.create_table(
        "reservation_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("confirmed_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
    )
    op.create_index("idx_reservation_items_reservation", "reservation_items", ["reservation_id"])
    op.create_index("idx_reservation_items_tenant", "reservation_items", ["tenant_id"])
    op.execute("ALTER TABLE reservation_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reservation_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON reservation_items "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── valuation_snapshots ───────────────────────────────────────────────────
    op.create_table(
        "valuation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("snapshot_cpp", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_snapshots_tenant_period", "valuation_snapshots", ["tenant_id", "period"])
    op.execute("ALTER TABLE valuation_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE valuation_snapshots FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON valuation_snapshots "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS valuation_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS reservation_items CASCADE")
    op.execute("DROP TABLE IF EXISTS reservations CASCADE")
