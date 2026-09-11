"""014 tenant external ref — identificar tenants aprovisionados por una plataforma externa

Revision ID: 014
Revises: 013
Create Date: 2026-09-11

Una sede creada desde Appits (Gestión-Talleres) nace como tenant propio en
Inventarios. Para que Appits pueda reconocerlo, no duplicarlo y darlo de baja,
el tenant guarda de quién viene (`external_provider`), qué id tiene allá
(`external_id`) y de qué taller principal cuelga (`parent_tenant_id`).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("external_provider", sa.String(50), nullable=True))
    op.add_column("tenants", sa.Column("external_id", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("tax_id", sa.String(50), nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "parent_tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # Un mismo id externo no puede corresponder a dos tenants: es lo que hace
    # idempotente el alta desde la plataforma (reintento ⇒ 409, no duplicado).
    op.create_index(
        "uq_tenants_external_ref",
        "tenants",
        ["external_provider", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_provider IS NOT NULL AND external_id IS NOT NULL"),
    )
    op.create_index("ix_tenants_parent_tenant_id", "tenants", ["parent_tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_tenants_parent_tenant_id", table_name="tenants")
    op.drop_index("uq_tenants_external_ref", table_name="tenants")
    op.drop_column("tenants", "parent_tenant_id")
    op.drop_column("tenants", "tax_id")
    op.drop_column("tenants", "external_id")
    op.drop_column("tenants", "external_provider")
