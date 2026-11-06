"""016 users — email único en toda la plataforma y cuenta raíz protegida

Revision ID: 016
Revises: 015
Create Date: 2026-11-06

Módulo 09 (gestión de usuarios), T-903.

1. El email pasa a ser único en TODA la plataforma y sin distinguir mayúsculas (RN-052-1,
   RN-052-2). Hasta ahora era único por tenant, pero el login lo busca en todos los tenants:
   con el mismo email en dos tenants, el login de ambos fallaba con 500.
2. `users.is_protected` marca la cuenta raíz de cada ambiente (L-1, RN-049-5): el super_admin
   activo existente. La migración SOLO lo marca; no cambia su email, contraseña, nombre ni estado.

Esta migración debe correr con MIGRATION_DATABASE_URL (rol owner), nunca con el rol de la app
(`inv_app`): ese rol vería 0 filas por RLS y la comprobación de duplicados no serviría.

Numeración: la definición del módulo 09 la llama «014», pero en esta rama 014 es
`tenant_external_ref` y 015 es la trazabilidad de lotes. Esta es la 016.
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # `users` tiene RLS FORCE. Se levanta el FORCE mientras corre la migración para que
    # también funcione si el rol de migración es dueño pero no superusuario (un superusuario
    # lo ignoraría de todos modos); sin esto las consultas verían 0 filas.
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")

    # 1. Abortar con un mensaje claro si hay emails duplicados (a 2026-11-05 no había ninguno en prod).
    duplicados = bind.execute(
        sa.text("SELECT lower(trim(email)) FROM users GROUP BY 1 HAVING count(*) > 1")
    ).fetchall()
    if duplicados:
        raise RuntimeError(
            "Emails duplicados (sin distinguir mayúsculas), resolver a mano antes de migrar: "
            f"{[d[0] for d in duplicados]}"
        )

    # 2. Normalizar a minúsculas y sin espacios.
    op.execute("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email))")

    # 3. Único en toda la plataforma. El índice `(tenant_id, email)` existente se mantiene.
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    # 4. Cuenta raíz protegida (L-1).
    op.add_column(
        "users",
        sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE users SET is_protected = true WHERE role = 'super_admin' AND is_active")

    protegidas = bind.execute(sa.text("SELECT count(*) FROM users WHERE is_protected")).scalar()
    super_admins = bind.execute(sa.text("SELECT count(*) FROM users WHERE role = 'super_admin'")).scalar()
    # Una base nueva no tiene ningún super_admin: el bootstrap creará el primero ya protegido.
    # Solo es un error que existan super_admins y ninguno esté activo: no habría cuenta raíz que marcar.
    if super_admins and not protegidas:
        raise RuntimeError("Hay super_admins pero ninguno activo que proteger: revisar antes de migrar")

    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_column("users", "is_protected")
    op.drop_index("uq_users_email_lower", table_name="users")
