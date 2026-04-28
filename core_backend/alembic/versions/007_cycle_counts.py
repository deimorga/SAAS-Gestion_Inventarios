"""007 cycle_counts — cycle_count_sessions y cycle_count_items

Revision ID: 007
Revises: 006
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── cycle_count_sessions ──────────────────────────────────────────────────
    op.create_table(
        "cycle_count_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'OPEN'"),
        sa.Column("apply_adjustments", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_cycle_sessions_tenant", "cycle_count_sessions", ["tenant_id", "status"])
    op.execute("ALTER TABLE cycle_count_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cycle_count_sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON cycle_count_sessions "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── cycle_count_items ─────────────────────────────────────────────────────
    op.create_table(
        "cycle_count_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("cycle_count_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expected_qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("counted_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_cycle_items_session", "cycle_count_items", ["session_id"])
    op.create_index("idx_cycle_items_tenant", "cycle_count_items", ["tenant_id"])
    op.execute("ALTER TABLE cycle_count_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE cycle_count_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON cycle_count_items "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cycle_count_items CASCADE")
    op.execute("DROP TABLE IF EXISTS cycle_count_sessions CASCADE")
