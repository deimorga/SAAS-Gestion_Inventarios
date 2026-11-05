"""Validaciones compartidas de trazabilidad: ubicación (bin), proveedor y lote.

Las usan los movimientos de inventario y las reservas. Todas filtran por tenant
además de RLS: un bin o proveedor de otro tenant es, para el que pregunta, inexistente.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.bin import Bin
from app.models.product import Product
from app.models.supplier import Supplier


def eq_or_null(column, value):
    """`column = value`, o `column IS NULL` cuando value es None (NULL nunca es igual a NULL en SQL)."""
    return column.is_(None) if value is None else column == value


def opt_str(value) -> str | None:
    return None if value is None else str(value)


async def get_bin_in_zone(db: AsyncSession, bin_id, zone_id, tenant_id: str) -> Bin | None:
    """Valida que el bin exista en el tenant, pertenezca a la zona indicada y esté activo."""
    if bin_id is None:
        return None
    result = await db.execute(select(Bin).where(Bin.id == str(bin_id), Bin.tenant_id == tenant_id))
    bin_ = result.scalar_one_or_none()
    if bin_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ubicación (bin) {bin_id} no encontrada")
    if str(bin_.zone_id) != str(zone_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La ubicación {bin_.code} no pertenece a la zona indicada",
        )
    if not bin_.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La ubicación {bin_.code} está inactiva",
        )
    return bin_


async def get_supplier_of_tenant(db: AsyncSession, supplier_id, tenant_id: str) -> Supplier | None:
    if supplier_id is None:
        return None
    result = await db.execute(
        select(Supplier).where(Supplier.id == str(supplier_id), Supplier.tenant_id == tenant_id)
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor {supplier_id} no encontrado")
    return supplier


def require_lot(product: Product, lot_number: str | None) -> None:
    """Un producto con track_lots no puede entrar, ajustarse ni trasladarse sin lote."""
    if product.track_lots and not lot_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"El producto {product.sku} maneja lotes (track_lots = true): "
                "el ítem debe incluir lot_number."
            ),
        )


def balance_supplier(lot_number: str | None, supplier_id) -> str | None:
    """El proveedor forma parte de la clave del saldo solo cuando hay lote.

    El proveedor distingue lotes (el mismo número de dos proveedores son lotes
    distintos), pero no parte el stock suelto: así una salida sin lote nunca se
    vuelve ambigua por haber recibido de dos proveedores.
    """
    return opt_str(supplier_id) if lot_number else None


async def ensure_batch(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    lot_number: str,
    supplier_id: str | None,
    expiry_date,
    quantity: Decimal,
) -> Batch:
    """Busca el lote (producto + proveedor + número) o lo crea con lo que trae la entrada."""
    result = await db.execute(
        select(Batch).where(
            Batch.tenant_id == tenant_id,
            Batch.product_id == product_id,
            Batch.batch_number == lot_number,
            eq_or_null(Batch.supplier_id, supplier_id),
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        batch = Batch(
            tenant_id=tenant_id,
            product_id=product_id,
            batch_number=lot_number,
            supplier_id=supplier_id,
            expiry_date=expiry_date,
            initial_qty=quantity,
            created_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        await db.flush()
    elif batch.expiry_date is None and expiry_date is not None:
        batch.expiry_date = expiry_date
    return batch


async def next_document_number(db: AsyncSession, tenant_id: str, doc_type: str = "RECEIPT", prefix: str = "E") -> str:
    """Siguiente consecutivo del tenant (E-000058).

    El UPSERT bloquea la fila del contador hasta el commit: dos entradas simultáneas
    no pueden recibir el mismo número, y un rollback devuelve el número (sin huecos).
    """
    row = (
        await db.execute(
            text(
                "INSERT INTO document_sequences (tenant_id, doc_type, last_value) VALUES (:tid, :dt, 1) "
                "ON CONFLICT (tenant_id, doc_type) "
                "DO UPDATE SET last_value = document_sequences.last_value + 1 "
                "RETURNING last_value"
            ),
            {"tid": tenant_id, "dt": doc_type},
        )
    ).fetchone()
    return f"{prefix}-{row.last_value:06d}"
