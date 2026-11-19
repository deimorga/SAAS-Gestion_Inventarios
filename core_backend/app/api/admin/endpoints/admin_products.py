from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin, AuthContext
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.schemas.catalog import ProductCreate, ProductResponse, ProductUpdate
from app.schemas.common import PaginatedResponse
from app.schemas.batch import BatchResponse, BatchUpdate
from app.schemas.supplier import SupplierResponse
from app.services import product as product_service
from app.services import category as category_service
from app.services import batch as batch_service
from app.services import supplier as supplier_service
from app.services.login_throttle import client_ip

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
    "/tenants/{tenant_id}/suppliers",
    response_model=list[SupplierResponse],
    summary="Listar proveedores de un tenant",
    description=(
        "Todos los proveedores del tenant, activos e inactivos: un lote antiguo puede venir "
        "de un proveedor ya dado de baja y el panel debe poder nombrarlo."
    ),
)
async def admin_list_suppliers(
    tenant_id: str,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await supplier_service.list_suppliers(db=session, tenant_id=tenant_id, is_active=None)


@router.get(
    "/tenants/{tenant_id}/batches",
    response_model=list[BatchResponse],
    summary="Listar lotes de un tenant",
    description="Lotes registrados del tenant, filtrables por producto. El portal los usa para corregir vencimientos.",
)
async def admin_list_batches(
    tenant_id: str,
    product_id: str | None = Query(None, description="Filtrar por UUID de producto"),
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await batch_service.list_batches(session, tenant_id, product_id)


@router.patch(
    "/tenants/{tenant_id}/batches/{batch_id}",
    response_model=BatchResponse,
    summary="Corregir el vencimiento de un lote de un tenant",
    description=(
        "Mismo comportamiento que `PATCH /v1/batches/{id}`: cambia la fecha o la quita (`null`), y quitarla "
        "cuenta como «sin vencimiento» de verdad. Opera con el RLS del tenant: un lote de otro tenant da 404."
    ),
    responses={404: {"description": "Lote no encontrado en este tenant"}, 422: {"description": "Validación"}},
)
async def admin_update_batch(
    tenant_id: str,
    batch_id: str,
    body: BatchUpdate,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
):
    performed_by = {"type": "user", "id": auth.user_id, "role": "super_admin"}
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await batch_service.update_batch(
            batch_id, body, session, tenant_id, performed_by, await client_ip(request)
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

