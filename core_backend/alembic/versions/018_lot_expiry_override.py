"""018 lotes — vencimiento corregido a mano (`batches.expiry_overridden`)

Revision ID: 018
Revises: 017
Create Date: 2026-11-18

`PATCH /v1/batches/{id}` permite cambiar o quitar la fecha de vencimiento de un lote ya registrado.

Quitarla tiene que contar como «sin vencimiento» de verdad. Hasta ahora, un lote con la fecha vacía
la tomaba del ledger (reservas, detalle de la reserva y saldos) para los lotes anteriores a que las
entradas crearan lotes, y la siguiente entrada del mismo lote rellenaba una fecha vacía. Sin una marca
no hay forma de distinguir «nunca se registró» de «se quitó a propósito».

`expiry_overridden = true` significa «la fecha del lote la corrigió una persona»: manda aunque esté
vacía, no se rellena desde el ledger ni desde nuevas entradas. Todo lo existente queda en `false` y no
cambia de comportamiento. El ledger no se toca (es inmutable).
"""

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column("expiry_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("batches", "expiry_overridden")
