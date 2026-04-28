"""006 webhooks — webhook_endpoints y webhook_deliveries

Revision ID: 006
Revises: 005
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── webhook_endpoints ─────────────────────────────────────────────────────
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("events", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_webhook_endpoints_tenant", "webhook_endpoints", ["tenant_id", "is_active"])
    op.execute("ALTER TABLE webhook_endpoints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_endpoints FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON webhook_endpoints "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )

    # ── webhook_deliveries ────────────────────────────────────────────────────
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'PENDING'"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_response_code", sa.Integer(), nullable=True),
        sa.Column("last_response_body", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_webhook_deliveries_dispatch", "webhook_deliveries", ["status", "next_attempt_at"])
    op.create_index("idx_webhook_deliveries_tenant", "webhook_deliveries", ["tenant_id", "created_at"])
    op.execute("ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_deliveries FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON webhook_deliveries "
        "USING (tenant_id::text = current_setting('app.current_tenant', true))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_deliveries CASCADE")
    op.execute("DROP TABLE IF EXISTS webhook_endpoints CASCADE")
