from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.supplier import Supplier, SupplierProduct
from app.schemas.supplier import (
    SupplierCreate,
    SupplierProductCreate,
    SupplierProductResponse,
    SupplierProductUpdate,
    SupplierResponse,
    SupplierUpdate,
)


async def _get_supplier_or_404(db: AsyncSession, supplier_id: str, tenant_id: str) -> Supplier:
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
    )
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no encontrado")
    return supplier


async def create_supplier(body: SupplierCreate, db: AsyncSession, tenant_id: str) -> SupplierResponse:
    dup = await db.execute(
        select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.code == body.code)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El código '{body.code}' ya existe en este tenant")

    now = datetime.now(timezone.utc)
    supplier = Supplier(
        id=str(uuid4()),
        tenant_id=tenant_id,
        code=body.code,
        name=body.name,
        tax_id=body.tax_id,
        email=str(body.email) if body.email else None,
        phone=body.phone,
        address=body.address,
        contact_name=body.contact_name,
        currency=body.currency,
        payment_terms_days=body.payment_terms_days,
        is_active=True,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


async def list_suppliers(db: AsyncSession, tenant_id: str, is_active: bool = True) -> list[SupplierResponse]:
    query = select(Supplier).where(Supplier.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(Supplier.is_active.is_(is_active))
    query = query.order_by(Supplier.name)
    result = await db.execute(query)
    return [SupplierResponse.model_validate(s) for s in result.scalars().all()]


async def get_supplier(supplier_id: str, db: AsyncSession, tenant_id: str) -> SupplierResponse:
    supplier = await _get_supplier_or_404(db, supplier_id, tenant_id)
    return SupplierResponse.model_validate(supplier)


async def update_supplier(supplier_id: str, body: SupplierUpdate, db: AsyncSession, tenant_id: str) -> SupplierResponse:
    supplier = await _get_supplier_or_404(db, supplier_id, tenant_id)
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "email" and value is not None:
            value = str(value)
        setattr(supplier, field, value)
    supplier.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


async def deactivate_supplier(supplier_id: str, db: AsyncSession, tenant_id: str) -> None:
    supplier = await _get_supplier_or_404(db, supplier_id, tenant_id)
    supplier.is_active = False
    supplier.updated_at = datetime.now(timezone.utc)
    await db.commit()


# ── SupplierProduct (RF-012) ───────────────────────────────────────────────────

async def add_supplier_product(
    supplier_id: str, body: SupplierProductCreate, db: AsyncSession, tenant_id: str
) -> SupplierProductResponse:
    await _get_supplier_or_404(db, supplier_id, tenant_id)

    product_result = await db.execute(
        select(Product).where(Product.id == str(body.product_id), Product.tenant_id == tenant_id)
    )
    if product_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    dup = await db.execute(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.product_id == str(body.product_id),
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El producto ya está asociado a este proveedor")

    now = datetime.now(timezone.utc)
    sp = SupplierProduct(
        id=str(uuid4()),
        tenant_id=tenant_id,
        supplier_id=supplier_id,
        product_id=str(body.product_id),
        supplier_sku=body.supplier_sku,
        unit_cost=body.unit_cost,
        currency=body.currency,
        lead_time_days=body.lead_time_days,
        moq=body.moq,
        is_preferred=body.is_preferred,
        created_at=now,
        updated_at=now,
    )
    db.add(sp)
    await db.commit()
    await db.refresh(sp)
    return SupplierProductResponse.model_validate(sp)


async def list_supplier_products(supplier_id: str, db: AsyncSession, tenant_id: str) -> list[SupplierProductResponse]:
    await _get_supplier_or_404(db, supplier_id, tenant_id)
    result = await db.execute(
        select(SupplierProduct).where(SupplierProduct.supplier_id == supplier_id).order_by(SupplierProduct.is_preferred.desc())
    )
    return [SupplierProductResponse.model_validate(sp) for sp in result.scalars().all()]


async def update_supplier_product(
    supplier_id: str, sp_id: str, body: SupplierProductUpdate, db: AsyncSession, tenant_id: str
) -> SupplierProductResponse:
    await _get_supplier_or_404(db, supplier_id, tenant_id)
    result = await db.execute(
        select(SupplierProduct).where(SupplierProduct.id == sp_id, SupplierProduct.supplier_id == supplier_id)
    )
    sp = result.scalar_one_or_none()
    if sp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asociación proveedor-producto no encontrada")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(sp, field, value)
    sp.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(sp)
    return SupplierProductResponse.model_validate(sp)


async def delete_supplier_product(supplier_id: str, sp_id: str, db: AsyncSession, tenant_id: str) -> None:
    await _get_supplier_or_404(db, supplier_id, tenant_id)
    result = await db.execute(
        select(SupplierProduct).where(SupplierProduct.id == sp_id, SupplierProduct.supplier_id == supplier_id)
    )
    sp = result.scalar_one_or_none()
    if sp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asociación proveedor-producto no encontrada")
    await db.delete(sp)
    await db.commit()
