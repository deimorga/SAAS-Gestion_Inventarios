"""015 lot & location traceability — ubicación exacta (bin), proveedor del lote y desglose de reservas

Revision ID: 015
Revises: 014
Create Date: 2026-11-04

Appits (talleres) necesita saber dónde está cada repuesto (bodega → zona → bin),
de qué proveedor vino cada lote y en qué orden de servicio se consumió.

Identidad del lote = producto + proveedor + número de lote. Dos proveedores pueden
traer el mismo número sin chocar ni fusionar su stock.

Todo lo nuevo es opcional (NULL): el stock, los lotes y las reservas existentes no
cambian de clave ni de comportamiento.

- batches.supplier_id                  → el lote sabe de qué proveedor vino.
- stock_balances.bin_id / supplier_id  → el saldo se lleva por producto+zona+bin+lote+proveedor.
- inventory_ledger.bin_id / supplier_id → cada movimiento guarda ubicación y proveedor.
- reservation_items.lot_number / bin_id / supplier_id → lo que pidió Appits.
- reservation_allocations              → lo que el inventario apartó de verdad (lote/bin/cantidad).
- transactions.document_number + document_sequences → consecutivo legible de entradas (E-000058).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# UUID "vacío" para que COALESCE trate NULL como un valor propio en los índices únicos.
_NIL = "'00000000-0000-0000-0000-000000000000'::uuid"
_UUID = postgresql.UUID(as_uuid=False)
_RLS_POLICY = "USING (tenant_id::text = current_setting('app.current_tenant', true))"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON {table} {_RLS_POLICY}")


def upgrade() -> None:
    # ── batches: proveedor del lote ──────────────────────────────────────────
    op.add_column("batches", sa.Column("supplier_id", _UUID, sa.ForeignKey("suppliers.id"), nullable=True))
    op.drop_constraint("uq_batches_tenant_product_number", "batches", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_batches_tenant_product_supplier_number "
        f"ON batches (tenant_id, product_id, COALESCE(supplier_id, {_NIL}), batch_number)"
    )
    op.create_index("idx_batches_tenant_supplier", "batches", ["tenant_id", "supplier_id"])

    # ── stock_balances: bin y proveedor en la clave del saldo ─────────────────
    op.add_column("stock_balances", sa.Column("bin_id", _UUID, sa.ForeignKey("bins.id"), nullable=True))
    op.add_column("stock_balances", sa.Column("supplier_id", _UUID, sa.ForeignKey("suppliers.id"), nullable=True))
    op.execute("DROP INDEX IF EXISTS idx_stock_product_zone_lot")
    # Las filas existentes tienen bin y proveedor NULL: conservan exactamente su clave.
    op.execute(
        "CREATE UNIQUE INDEX idx_stock_product_zone_bin_lot_supplier ON stock_balances "
        f"(tenant_id, product_id, zone_id, COALESCE(bin_id, {_NIL}), "
        f"COALESCE(lot_number, 'N/A'), COALESCE(supplier_id, {_NIL}))"
    )
    op.create_index("idx_stock_tenant_bin", "stock_balances", ["tenant_id", "bin_id"])
    op.create_index("idx_stock_tenant_lot", "stock_balances", ["tenant_id", "lot_number"])

    # ── inventory_ledger: ubicación y proveedor de cada movimiento ───────────
    # Solo se agregan columnas (NULL en el histórico): ninguna fila existente se modifica.
    op.add_column("inventory_ledger", sa.Column("bin_id", _UUID, sa.ForeignKey("bins.id"), nullable=True))
    op.add_column("inventory_ledger", sa.Column("supplier_id", _UUID, sa.ForeignKey("suppliers.id"), nullable=True))
    op.create_index("idx_ledger_tenant_lot", "inventory_ledger", ["tenant_id", "lot_number"])
    op.create_index("idx_ledger_tenant_bin", "inventory_ledger", ["tenant_id", "bin_id"])
    op.create_index("idx_ledger_tenant_reference", "inventory_ledger", ["tenant_id", "reference_id"])

    # ── reservation_items: lo que pidió el cliente ───────────────────────────
    op.add_column("reservation_items", sa.Column("lot_number", sa.String(100), nullable=True))
    op.add_column("reservation_items", sa.Column("bin_id", _UUID, sa.ForeignKey("bins.id"), nullable=True))
    op.add_column("reservation_items", sa.Column("supplier_id", _UUID, sa.ForeignKey("suppliers.id"), nullable=True))

    # ── reservation_allocations: lo que se apartó de verdad ──────────────────
    op.create_table(
        "reservation_allocations",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "reservation_item_id", _UUID,
            sa.ForeignKey("reservation_items.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("stock_balance_id", _UUID, sa.ForeignKey("stock_balances.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("lot_number", sa.String(100), nullable=True),
        sa.Column("bin_id", _UUID, sa.ForeignKey("bins.id"), nullable=True),
        sa.Column("supplier_id", _UUID, sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("confirmed_qty", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_res_alloc_item", "reservation_allocations", ["reservation_item_id", "seq"])
    op.create_index("idx_res_alloc_tenant_lot", "reservation_allocations", ["tenant_id", "lot_number"])
    _enable_rls("reservation_allocations")

    # ── Consecutivo de entradas (E-000058) ───────────────────────────────────
    op.add_column("transactions", sa.Column("document_number", sa.String(30), nullable=True))
    op.create_index(
        "uq_transactions_tenant_document_number", "transactions", ["tenant_id", "document_number"],
        unique=True, postgresql_where=sa.text("document_number IS NOT NULL"),
    )
    op.create_table(
        "document_sequences",
        sa.Column("tenant_id", _UUID, sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("doc_type", sa.String(30), primary_key=True),
        sa.Column("last_value", sa.Integer, nullable=False),
    )
    _enable_rls("document_sequences")

    # Numerar las entradas históricas por tenant en orden cronológico, para que la
    # secuencia continúe donde terminan. `transactions` tiene RLS FORCE: se levanta
    # el FORCE durante el relleno para que también funcione si el rol de migración
    # es dueño pero no superusuario (un superusuario lo ignoraría de todos modos).
    op.execute("ALTER TABLE transactions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_sequences NO FORCE ROW LEVEL SECURITY")
    op.execute(
        "UPDATE transactions t SET document_number = 'E-' || lpad(x.rn::text, 6, '0') "
        "FROM (SELECT id, row_number() OVER (PARTITION BY tenant_id ORDER BY created_at, id) AS rn "
        "      FROM transactions WHERE transaction_type = 'RECEIPT') x "
        "WHERE t.id = x.id"
    )
    op.execute(
        "INSERT INTO document_sequences (tenant_id, doc_type, last_value) "
        "SELECT tenant_id, 'RECEIPT', count(*) FROM transactions "
        "WHERE transaction_type = 'RECEIPT' GROUP BY tenant_id"
    )
    op.execute("ALTER TABLE document_sequences FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE transactions FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("document_sequences")
    op.drop_index("uq_transactions_tenant_document_number", table_name="transactions")
    op.drop_column("transactions", "document_number")

    op.drop_table("reservation_allocations")
    op.drop_column("reservation_items", "supplier_id")
    op.drop_column("reservation_items", "bin_id")
    op.drop_column("reservation_items", "lot_number")

    op.drop_index("idx_ledger_tenant_reference", table_name="inventory_ledger")
    op.drop_index("idx_ledger_tenant_bin", table_name="inventory_ledger")
    op.drop_index("idx_ledger_tenant_lot", table_name="inventory_ledger")
    op.drop_column("inventory_ledger", "supplier_id")
    op.drop_column("inventory_ledger", "bin_id")

    # Volver a la clave anterior falla si ya hay saldos que solo se distinguen por bin
    # o proveedor: en ese caso hay que consolidarlos antes de bajar la versión.
    op.drop_index("idx_stock_tenant_lot", table_name="stock_balances")
    op.drop_index("idx_stock_tenant_bin", table_name="stock_balances")
    op.execute("DROP INDEX IF EXISTS idx_stock_product_zone_bin_lot_supplier")
    op.execute(
        "CREATE UNIQUE INDEX idx_stock_product_zone_lot "
        "ON stock_balances(tenant_id, product_id, zone_id, COALESCE(lot_number, 'N/A'))"
    )
    op.drop_column("stock_balances", "supplier_id")
    op.drop_column("stock_balances", "bin_id")

    op.drop_index("idx_batches_tenant_supplier", table_name="batches")
    op.execute("DROP INDEX IF EXISTS uq_batches_tenant_product_supplier_number")
    op.create_unique_constraint("uq_batches_tenant_product_number", "batches", ["tenant_id", "product_id", "batch_number"])
    op.drop_column("batches", "supplier_id")
