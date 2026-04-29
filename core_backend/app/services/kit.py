from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kit_component import KitComponent
from app.models.product import Product


async def _get_product_or_404(db: AsyncSession, product_id: str, tenant_id: str) -> Product:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.is_active.is_(True))
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return p


async def list_components(kit_product_id: str, db: AsyncSession, tenant_id: str) -> list[dict]:
    await _get_product_or_404(db, kit_product_id, tenant_id)
    result = await db.execute(
        select(KitComponent, Product)
        .join(Product, KitComponent.component_product_id == Product.id)
        .where(KitComponent.kit_product_id == kit_product_id)
        .order_by(Product.name)
    )
    rows = result.all()
    return [
        {
            "id": kc.id,
            "kit_product_id": kc.kit_product_id,
            "component_product_id": kc.component_product_id,
            "component_sku": p.sku,
            "component_name": p.name,
            "component_uom": p.base_uom,
            "quantity": kc.quantity,
        }
        for kc, p in rows
    ]


async def add_component(
    kit_product_id: str,
    component_product_id: str,
    quantity: Decimal,
    db: AsyncSession,
    tenant_id: str,
) -> dict:
    kit = await _get_product_or_404(db, kit_product_id, tenant_id)
    component = await _get_product_or_404(db, component_product_id, tenant_id)

    if kit_product_id == component_product_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Un kit no puede ser componente de sí mismo")

    if component.is_kit:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se permiten kits anidados: el componente es un kit")

    dup = await db.execute(
        select(KitComponent).where(
            KitComponent.kit_product_id == kit_product_id,
            KitComponent.component_product_id == component_product_id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El componente ya existe en este kit")

    kc = KitComponent(
        id=str(uuid4()),
        kit_product_id=kit_product_id,
        component_product_id=component_product_id,
        quantity=quantity,
    )
    db.add(kc)

    if not kit.is_kit:
        kit.is_kit = True

    await db.commit()
    await db.refresh(kc)

    return {
        "id": kc.id,
        "kit_product_id": kc.kit_product_id,
        "component_product_id": kc.component_product_id,
        "component_sku": component.sku,
        "component_name": component.name,
        "component_uom": component.base_uom,
        "quantity": kc.quantity,
    }


async def remove_component(kit_product_id: str, component_id: str, db: AsyncSession, tenant_id: str) -> None:
    await _get_product_or_404(db, kit_product_id, tenant_id)
    result = await db.execute(
        select(KitComponent).where(
            KitComponent.id == component_id,
            KitComponent.kit_product_id == kit_product_id,
        )
    )
    kc = result.scalar_one_or_none()
    if kc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Componente no encontrado en este kit")
    await db.delete(kc)

    remaining = await db.execute(
        select(KitComponent).where(KitComponent.kit_product_id == kit_product_id)
    )
    if not remaining.scalars().first():
        kit_result = await db.execute(
            select(Product).where(Product.id == kit_product_id)
        )
        kit = kit_result.scalar_one_or_none()
        if kit:
            kit.is_kit = False

    await db.commit()
