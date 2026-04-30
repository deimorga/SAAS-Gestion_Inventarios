"""012 admin bootstrap — must_change_password, created_by, last_used_at, RLS bypass, seed micronuba-internal

Revision ID: 012
Revises: 011
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

# UUID fijo del tenant interno de MicroNuba — nunca cambiar
MICRONUBA_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# Sentinel que activa el bypass de RLS para super_admin
SUPER_ADMIN_SENTINEL = "__super_admin__"

_RLS_BYPASS_POLICY = (
    "USING ("
    f"  current_setting('app.current_tenant', true) = '{SUPER_ADMIN_SENTINEL}'"
    "  OR tenant_id::text = current_setting('app.current_tenant', true)"
    ")"
)


def upgrade() -> None:
    # ── 1. Nuevas columnas en users ────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True),
    )

    # ── 2. Nueva columna en api_keys ───────────────────────────────────────
    op.add_column(
        "api_keys",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 3. Actualizar política RLS — users ────────────────────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute(
        "CREATE POLICY tenant_isolation ON users " + _RLS_BYPASS_POLICY
    )

    # ── 4. Actualizar política RLS — api_keys ─────────────────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON api_keys")
    op.execute(
        "CREATE POLICY tenant_isolation ON api_keys " + _RLS_BYPASS_POLICY
    )

    # ── 5. Actualizar política RLS — audit_logs ───────────────────────────
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs")
    op.execute(
        "CREATE POLICY tenant_isolation ON audit_logs " + _RLS_BYPASS_POLICY
    )

    # ── 6. Seed: tenant interno MicroNuba ─────────────────────────────────
    op.execute(f"""
        INSERT INTO tenants (id, name, slug, subscription_tier, config, is_active, created_at, updated_at)
        VALUES (
            '{MICRONUBA_TENANT_ID}',
            'MicroNuba Internal',
            'micronuba-internal',
            'ENTERPRISE',
            '{{"api_key_rotation_grace_days": 30}}',
            true,
            now(),
            now()
        )
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    # Eliminar seed
    op.execute(f"DELETE FROM tenants WHERE id = '{MICRONUBA_TENANT_ID}'")

    # Restaurar políticas RLS originales (sin bypass)
    _ORIGINAL = "USING (tenant_id::text = current_setting('app.current_tenant', true))"

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs")
    op.execute("CREATE POLICY tenant_isolation ON audit_logs " + _ORIGINAL)

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON api_keys")
    op.execute("CREATE POLICY tenant_isolation ON api_keys " + _ORIGINAL)

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("CREATE POLICY tenant_isolation ON users " + _ORIGINAL)

    # Eliminar columnas
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("users", "created_by")
    op.drop_column("users", "must_change_password")
