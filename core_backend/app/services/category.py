import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.product import Product
from app.schemas.catalog import CategoryCreate, CategoryResponse, CategoryTreeNode, CategoryUpdate


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII)
    return re.sub(r"[\s_-]+", "-", text)


async def _build_path(parent_id: str | None, name: str, db: AsyncSession) -> str:
    if parent_id is None:
        return name
    result = await db.execute(select(Category).where(Category.id == parent_id))
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Categoría padre no encontrada")
    return f"{parent.path} / {name}"


async def create_category(body: CategoryCreate, db: AsyncSession, tenant_id: str) -> CategoryResponse:
    # Verificar nombre único en el mismo nivel
    dup = await db.execute(
        select(Category).where(
            Category.tenant_id == tenant_id,
            Category.parent_id == (str(body.parent_id) if body.parent_id else None),
            Category.name == body.name,
            Category.is_active.is_(True),
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una categoría con ese nombre en este nivel")

    path = await _build_path(str(body.parent_id) if body.parent_id else None, body.name, db)
    now = datetime.now(timezone.utc)

    cat = Category(
        id=str(uuid4()),
        tenant_id=tenant_id,
        parent_id=str(body.parent_id) if body.parent_id else None,
        name=body.name,
        slug=_slugify(body.name),
        path=path,
        sort_order=body.sort_order,
        is_active=True,
        created_at=now,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return _to_response(cat, 0, 0)


async def list_categories(db: AsyncSession, tenant_id: str, flat: bool, include_counts: bool):
    result = await db.execute(
        select(Category)
        .where(Category.tenant_id == tenant_id, Category.is_active.is_(True))
        .order_by(Category.sort_order, Category.name)
    )
    cats = result.scalars().all()

    counts: dict[str, int] = {}
    if include_counts:
        cnt_result = await db.execute(
            select(Product.category_id, func.count(Product.id))
            .where(Product.tenant_id == tenant_id, Product.is_active.is_(True))
            .group_by(Product.category_id)
        )
        counts = {row[0]: row[1] for row in cnt_result.all()}

    children_count: dict[str, int] = {}
    for c in cats:
        if c.parent_id:
            children_count[c.parent_id] = children_count.get(c.parent_id, 0) + 1

    if flat:
        return [_to_response(c, children_count.get(c.id, 0), counts.get(c.id, 0)) for c in cats]

    return _build_tree(cats, children_count, counts, None)


def _build_tree(cats, children_count, counts, parent_id) -> list[CategoryTreeNode]:
    nodes = []
    for c in cats:
        if c.parent_id == parent_id:
            node = CategoryTreeNode(
                **_to_response(c, children_count.get(c.id, 0), counts.get(c.id, 0)).model_dump(),
                children=_build_tree(cats, children_count, counts, c.id),
            )
            nodes.append(node)
    return nodes


async def get_category(cat_id: str, db: AsyncSession, tenant_id: str) -> CategoryResponse:
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.tenant_id == tenant_id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    children_count = await db.scalar(
        select(func.count(Category.id)).where(Category.parent_id == cat_id, Category.is_active.is_(True))
    ) or 0
    products_count = await db.scalar(
        select(func.count(Product.id)).where(Product.category_id == cat_id, Product.is_active.is_(True))
    ) or 0
    return _to_response(cat, children_count, products_count)


async def update_category(cat_id: str, body: CategoryUpdate, db: AsyncSession, tenant_id: str) -> CategoryResponse:
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.tenant_id == tenant_id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    if body.name is not None:
        cat.name = body.name
        cat.slug = _slugify(body.name)
        cat.path = await _build_path(cat.parent_id, body.name, db)
    if body.sort_order is not None:
        cat.sort_order = body.sort_order

    await db.commit()
    await db.refresh(cat)
    return _to_response(cat, 0, 0)


async def delete_category(cat_id: str, db: AsyncSession, tenant_id: str) -> None:
    result = await db.execute(select(Category).where(Category.id == cat_id, Category.tenant_id == tenant_id))
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Categoría no encontrada")

    subcats = await db.scalar(
        select(func.count(Category.id)).where(Category.parent_id == cat_id, Category.is_active.is_(True))
    ) or 0
    if subcats > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La categoría tiene subcategorías activas")

    prods = await db.scalar(
        select(func.count(Product.id)).where(Product.category_id == cat_id, Product.is_active.is_(True))
    ) or 0
    if prods > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La categoría tiene productos asignados")

    cat.is_active = False
    await db.commit()


def _to_response(cat: Category, children_count: int, products_count: int) -> CategoryResponse:
    return CategoryResponse(
        id=cat.id,
        tenant_id=cat.tenant_id,
        name=cat.name,
        parent_id=cat.parent_id,
        path=cat.path,
        slug=cat.slug,
        sort_order=cat.sort_order,
        is_active=cat.is_active,
        children_count=children_count,
        products_count=products_count,
    )
