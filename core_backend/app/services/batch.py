from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch, SerialNumber
from app.models.product import Product
from app.schemas.batch import (
    BatchCreate,
    BatchResponse,
    SerialNumberBulkCreate,
    SerialNumberResponse,
    SerialStatusResponse,
)


async def _get_product_or_404(db: AsyncSession, product_id: str, tenant_id: str) -> Product:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.is_active.is_(True))
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return p


async def create_batch(body: BatchCreate, db: AsyncSession, tenant_id: str) -> BatchResponse:
    product = await _get_product_or_404(db, str(body.product_id), tenant_id)

    if not product.track_lots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El producto no tiene trazabilidad de lotes habilitada (`track_lots=false`)",
        )

    dup = await db.execute(
        select(Batch).where(
            Batch.tenant_id == tenant_id,
            Batch.product_id == str(body.product_id),
            Batch.batch_number == body.batch_number,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El número de lote '{body.batch_number}' ya existe para este producto")

    now = datetime.now(timezone.utc)
    batch = Batch(
        id=str(uuid4()),
        tenant_id=tenant_id,
        product_id=str(body.product_id),
        batch_number=body.batch_number,
        manufactured_date=body.manufactured_date,
        expiry_date=body.expiry_date,
        initial_qty=body.initial_qty,
        notes=body.notes,
        created_at=now,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return BatchResponse.model_validate(batch)


async def list_batches(db: AsyncSession, tenant_id: str, product_id: str | None = None) -> list[BatchResponse]:
    query = select(Batch).where(Batch.tenant_id == tenant_id)
    if product_id:
        query = query.where(Batch.product_id == product_id)
    query = query.order_by(Batch.created_at.desc())
    result = await db.execute(query)
    return [BatchResponse.model_validate(b) for b in result.scalars().all()]


async def get_batch(batch_id: str, db: AsyncSession, tenant_id: str) -> BatchResponse:
    result = await db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id)
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")
    return BatchResponse.model_validate(batch)


# ── Serial Numbers ─────────────────────────────────────────────────────────────

async def add_serials(batch_id: str, body: SerialNumberBulkCreate, db: AsyncSession, tenant_id: str) -> list[SerialNumberResponse]:
    batch_result = await db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id)
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")

    product = await _get_product_or_404(db, batch.product_id, tenant_id)
    if not product.track_serials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El producto no tiene trazabilidad de seriales habilitada (`track_serials=false`)",
        )

    sn_values = [s.serial_number for s in body.serials]
    dup_result = await db.execute(
        select(SerialNumber.serial_number).where(
            SerialNumber.tenant_id == tenant_id,
            SerialNumber.serial_number.in_(sn_values),
        )
    )
    duplicates = [row[0] for row in dup_result.all()]
    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Los siguientes seriales ya existen: {', '.join(duplicates)}",
        )

    now = datetime.now(timezone.utc)
    created = []
    for s in body.serials:
        sn = SerialNumber(
            id=str(uuid4()),
            tenant_id=tenant_id,
            product_id=batch.product_id,
            batch_id=batch_id,
            serial_number=s.serial_number,
            status="AVAILABLE",
            notes=s.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(sn)
        created.append(sn)

    await db.commit()
    for sn in created:
        await db.refresh(sn)
    return [SerialNumberResponse.model_validate(sn) for sn in created]


async def list_serials(batch_id: str, db: AsyncSession, tenant_id: str) -> list[SerialNumberResponse]:
    batch_result = await db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id)
    )
    if batch_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado")

    result = await db.execute(
        select(SerialNumber).where(SerialNumber.batch_id == batch_id).order_by(SerialNumber.serial_number)
    )
    return [SerialNumberResponse.model_validate(sn) for sn in result.scalars().all()]


async def get_serial_status(serial_number: str, db: AsyncSession, tenant_id: str) -> SerialStatusResponse:
    result = await db.execute(
        select(SerialNumber).where(SerialNumber.serial_number == serial_number, SerialNumber.tenant_id == tenant_id)
    )
    sn = result.scalar_one_or_none()
    if sn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serial no encontrado")
    return SerialStatusResponse(
        serial_number=sn.serial_number,
        product_id=sn.product_id,
        batch_id=sn.batch_id,
        status=sn.status,
        is_available=sn.status == "AVAILABLE",
    )
