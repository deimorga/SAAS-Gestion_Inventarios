from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin, AuthContext
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.schemas.catalog import ProductCreate, ProductResponse, ProductUpdate
from app.schemas.common import PaginatedResponse
from app.services import product as product_service
from app.services import category as category_service

router = APIRouter(tags=["Admin — Productos"])


async def _tenant_db(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        yield session


@router.get(
    "/tenants/{tenant_id}/products",
    response_model=PaginatedResponse,
    summary="Listar productos de un tenant",
)
async def admin_list_products(
    tenant_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(lambda tenant_id=None: None),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await product_service.list_products(
            db=session,
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            search=search,
            category_id=None,
            is_active=True,
            track_serials=None,
            sort_by="name",
            sort_order="asc",
        )


@router.post(
    "/tenants/{tenant_id}/products",
    response_model=ProductResponse,
    status_code=201,
    summary="Crear producto en un tenant",
)
async def admin_create_product(
    tenant_id: str,
    body: ProductCreate,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await product_service.create_product(body=body, db=session, tenant_id=tenant_id)


@router.patch(
    "/tenants/{tenant_id}/products/{product_id}",
    response_model=ProductResponse,
    summary="Actualizar producto de un tenant",
)
async def admin_update_product(
    tenant_id: str,
    product_id: str,
    body: ProductUpdate,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await product_service.update_product(
            product_id=product_id, body=body, db=session, tenant_id=tenant_id
        )


@router.delete(
    "/tenants/{tenant_id}/products/{product_id}",
    status_code=204,
    summary="Desactivar producto de un tenant",
)
async def admin_delete_product(
    tenant_id: str,
    product_id: str,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        await product_service.deactivate_product(
            product_id=product_id, db=session, tenant_id=tenant_id
        )


@router.get(
    "/tenants/{tenant_id}/categories",
    response_model=list,
    summary="Listar categorías de un tenant",
)
async def admin_list_categories(
    tenant_id: str,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await category_service.list_categories(
            db=session, tenant_id=tenant_id, flat=True, include_counts=True,
        )

