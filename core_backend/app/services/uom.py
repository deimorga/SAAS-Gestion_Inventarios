from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_uom import ProductUom
from app.schemas.catalog import ProductUomCreate, ProductUomResponse


async def list_uoms(product_id: str, db: AsyncSession, tenant_id: str) -> list[ProductUomResponse]:
    # Verificar que el producto pertenece al tenant
    prod = await db.execute(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    if prod.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    result = await db.execute(select(ProductUom).where(ProductUom.product_id == product_id))
    return [ProductUomResponse.model_validate(u) for u in result.scalars().all()]


async def add_uom(product_id: str, body: ProductUomCreate, db: AsyncSession, tenant_id: str) -> ProductUomResponse:
    prod_result = await db.execute(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    if prod_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    dup = await db.execute(
        select(ProductUom).where(ProductUom.product_id == product_id, ProductUom.uom_code == body.uom_code)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El código UOM '{body.uom_code}' ya existe para este producto")

    uom = ProductUom(
        id=str(uuid4()),
        product_id=product_id,
        uom_code=body.uom_code,
        conversion_factor=body.conversion_factor,
        is_purchase_uom=body.is_purchase_uom,
        is_sale_uom=body.is_sale_uom,
    )
    db.add(uom)
    await db.commit()
    await db.refresh(uom)
    return ProductUomResponse.model_validate(uom)


async def delete_uom(product_id: str, uom_id: str, db: AsyncSession, tenant_id: str) -> None:
    prod_result = await db.execute(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    if prod_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    result = await db.execute(select(ProductUom).where(ProductUom.id == uom_id, ProductUom.product_id == product_id))
    uom = result.scalar_one_or_none()
    if uom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversión UOM no encontrada")

    await db.delete(uom)
    await db.commit()
