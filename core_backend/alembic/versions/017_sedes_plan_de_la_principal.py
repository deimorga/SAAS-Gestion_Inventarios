"""017 sedes — el plan lo define su tenant principal

Revision ID: 017
Revises: 016
Create Date: 2026-11-11

El plan (`tenants.subscription_tier`) fija las peticiones por minuto de cada tenant (60, 1.000 o
10.000). Cada sede es un tenant aparte, y hasta ahora todas nacían en STARTER aunque su principal
tuviera otro plan.

Desde esta versión una sede **toma el plan de su principal**: se cambia solo ahí, y el cambio
arrastra a sus sedes. Esta migración alinea las sedes que ya existen. Solo toca los datos: no
cambia el esquema.

Ojo al desplegar: las sedes cuyo plan guardado difería del de su principal pasan a tener el de la
principal, y con él su límite de peticiones por minuto.
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `tenants` no está bajo RLS. Solo sedes cuya principal existe; las demás conservan su plan.
    op.execute(
        "UPDATE tenants c SET subscription_tier = p.subscription_tier "
        "FROM tenants p "
        "WHERE c.parent_tenant_id = p.id AND c.subscription_tier <> p.subscription_tier"
    )


def downgrade() -> None:
    # El plan anterior de cada sede no se guardó: no hay a qué volver. Bajar la versión no
    # revierte nada; las sedes conservan el plan de su principal.
    pass
