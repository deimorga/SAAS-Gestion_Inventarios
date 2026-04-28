from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.product import Product
from app.schemas.catalog import CategorySummary, ProductCreate, ProductListItem, ProductResponse, ProductUpdate
from app.schemas.common import PaginatedResponse, PaginationMeta

_SORT_FIELDS = {"name": Product.name, "sku": Product.sku, "created_at": Product.created_at, "updated_at": Product.updated_at}


async def _fetch_category(db: AsyncSession, category_id: str | None, tenant_id: str) -> Category | None:
    if not category_id:
        return None
    result = await db.execute(select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id))
    return result.scalar_one_or_none()


async def create_product(body: ProductCreate, db: AsyncSession, tenant_id: str) -> ProductResponse:
    dup = await db.execute(select(Product).where(Product.tenant_id == tenant_id, Product.sku == body.sku))
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El SKU '{body.sku}' ya existe en este tenant",
        )

    category = None
    if body.category_id:
        category = await _fetch_category(db, str(body.category_id), tenant_id)
        if category is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Categoría no encontrada")

    now = datetime.now(timezone.utc)
    product = Product(
        id=str(uuid4()),
        tenant_id=tenant_id,
        category_id=str(body.category_id) if body.category_id else None,
        sku=body.sku,
        name=body.name,
        description=body.description,
        base_uom=body.base_uom,
        current_cpp=Decimal("0"),
        reorder_point=body.reorder_point,
        track_serials=body.track_serials,
        track_lots=body.track_lots,
        track_expiry=body.track_expiry,
        is_kit=False,
        is_active=True,
        low_stock_alert_enabled=body.low_stock_alert_enabled,
        metadata_=body.metadata,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _to_response(product, category)


async def list_products(
    db: AsyncSession,
    tenant_id: str,
    page: int,
    page_size: int,
    search: str | None,
    category_id: str | None,
    is_active: bool,
    track_serials: bool | None,
    sort_by: str,
    sort_order: str,
) -> PaginatedResponse:
    query = select(Product).where(Product.tenant_id == tenant_id, Product.is_active.is_(is_active))

    if search:
        term = f"%{search}%"
        query = query.where(or_(Product.sku.ilike(term), Product.name.ilike(term), Product.description.ilike(term)))

    if category_id:
        cat_result = await db.execute(select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id))
        cat = cat_result.scalar_one_or_none()
        if cat:
            sub_cats = await db.execute(
                select(Category.id).where(Category.tenant_id == tenant_id, Category.path.startswith(cat.path), Category.is_active.is_(True))
            )
            cat_ids = [row[0] for row in sub_cats.all()]
            query = query.where(Product.category_id.in_(cat_ids))

    if track_serials is not None:
        query = query.where(Product.track_serials.is_(track_serials))

    sort_col = _SORT_FIELDS.get(sort_by, Product.created_at)
    query = query.order_by(asc(sort_col) if sort_order == "asc" else desc(sort_col))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    rows = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    products = rows.scalars().all()

    # Fetch categories in bulk
    cat_ids_needed = {p.category_id for p in products if p.category_id}
    categories: dict[str, Category] = {}
    if cat_ids_needed:
        cat_rows = await db.execute(select(Category).where(Category.id.in_(cat_ids_needed)))
        categories = {c.id: c for c in cat_rows.scalars().all()}

    items = [
        ProductListItem(
            id=p.id, sku=p.sku, name=p.name,
            category=CategorySummary(id=categories[p.category_id].id, name=categories[p.category_id].name) if p.category_id and p.category_id in categories else None,
            base_uom=p.base_uom, current_cpp=p.current_cpp, reorder_point=p.reorder_point,
            is_active=p.is_active, is_kit=p.is_kit, created_at=p.created_at,
        )
        for p in products
    ]

    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total_items=total, total_pages=-(-total // page_size)),
    )


async def get_product(product_id: str, db: AsyncSession, tenant_id: str) -> ProductResponse:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    category = await _fetch_category(db, product.category_id, tenant_id)
    return _to_response(product, category)


async def update_product(product_id: str, body: ProductUpdate, db: AsyncSession, tenant_id: str) -> ProductResponse:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    updates = body.model_dump(exclude_none=True)
    category = await _fetch_category(db, product.category_id, tenant_id)

    if "category_id" in updates:
        if updates["category_id"] is not None:
            category = await _fetch_category(db, str(updates["category_id"]), tenant_id)
            if category is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Categoría no encontrada")
            product.category_id = str(updates["category_id"])
        else:
            product.category_id = None
            category = None

    for field, value in updates.items():
        if field == "category_id":
            continue
        if field == "metadata":
            product.metadata_ = value
        else:
            setattr(product, field, value)

    product.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(product)
    return _to_response(product, category)


async def deactivate_product(product_id: str, db: AsyncSession, tenant_id: str) -> None:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")

    product.is_active = False
    product.updated_at = datetime.now(timezone.utc)
    await db.commit()


def _to_response(product: Product, category: Category | None) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        tenant_id=product.tenant_id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        category=CategorySummary(id=category.id, name=category.name) if category else None,
        base_uom=product.base_uom,
        current_cpp=product.current_cpp,
        reorder_point=product.reorder_point,
        track_lots=product.track_lots,
        track_serials=product.track_serials,
        track_expiry=product.track_expiry,
        is_kit=product.is_kit,
        is_active=product.is_active,
        low_stock_alert_enabled=product.low_stock_alert_enabled,
        metadata=product.metadata_,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )
