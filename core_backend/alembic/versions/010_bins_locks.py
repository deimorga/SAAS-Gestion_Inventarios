"""010 bins_locks — zonificacion bins/slots y bloqueos de ubicacion

Revision ID: 010
Revises: 009
Create Date: 2026-04-28
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── bins ──────────────────────────────────────────────────────────────────
    op.create_table(
        "bins",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("max_weight_kg", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_volume_m3", sa.Numeric(10, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_bins_zone", "bins", ["zone_id", "is_active"])
    op.create_unique_constraint("uq_bins_zone_code", "bins", ["zone_id", "code"])

    op.execute("ALTER TABLE bins ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bins FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON bins "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── location_locks ────────────────────────────────────────────────────────
    op.create_table(
        "location_locks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bin_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("bins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("locked_by", sa.String(255), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("idx_location_locks_bin", "location_locks", ["bin_id", "is_active"])

    op.execute("ALTER TABLE location_locks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE location_locks FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON location_locks "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON location_locks")
    op.drop_table("location_locks")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON bins")
    op.drop_table("bins")
