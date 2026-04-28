from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_catalog_read, require_catalog_write
from app.schemas.catalog import ProductCreate, ProductResponse, ProductUomCreate, ProductUomResponse, ProductUpdate
from app.schemas.common import PaginatedResponse
from app.services.audit import log_action
from app.services.product import create_product, deactivate_product, get_product, list_products, update_product
from app.services.uom import add_uom, delete_uom, list_uoms

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="Listar productos",
    description=(
        "Retorna el catálogo de productos del tenant con soporte de búsqueda (ILIKE sobre SKU y nombre), "
        "filtros por categoría y estado, y ordenamiento configurable."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_products(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Registros por página"),
    search: str | None = Query(None, description="Búsqueda por SKU o nombre (ILIKE)"),
    category_id: str | None = Query(None, description="Filtrar por UUID de categoría"),
    is_active: bool = Query(True, description="Incluir solo productos activos"),
    track_serials: bool | None = Query(None, description="Filtrar por trazabilidad de seriales"),
    sort_by: str = Query("created_at", pattern="^(name|sku|created_at|updated_at)$", description="Campo de ordenamiento"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Dirección: asc | desc"),
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_products(db, auth.tenant_id, page, page_size, search, category_id, is_active, track_serials, sort_by, sort_order)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
    summary="Crear producto",
    description=(
        "Crea un nuevo SKU en el catálogo del tenant. "
        "El campo `base_uom` define la unidad base del producto; las conversiones se gestionan en `/uom`. "
        "El `current_cpp` inicia en 0 y se actualiza automáticamente con cada entrada (receipt)."
    ),
    responses={
        201: {"description": "Producto creado"},
        409: {"description": "SKU duplicado en el tenant"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def add_product(
    body: ProductCreate,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    product = await create_product(body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="products", entity_id=str(product.id),
        action="CREATE", new_values={"sku": product.sku, "name": product.name},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return product


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Obtener producto por ID",
    description="Retorna el detalle completo de un producto, incluyendo CPP actual y punto de reorden.",
    responses={
        404: {"description": "Producto no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_product_detail(
    product_id: str,
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_product(product_id, db, auth.tenant_id)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Actualizar producto",
    description="Actualiza parcialmente los campos del producto. Solo los campos enviados se modifican.",
    responses={
        404: {"description": "Producto no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def patch_product(
    product_id: str,
    body: ProductUpdate,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    old = await get_product(product_id, db, auth.tenant_id)
    updated = await update_product(product_id, body, db, auth.tenant_id)
    changes = body.model_dump(exclude_none=True)
    if changes:
        old_snapshot = jsonable_encoder({k: getattr(old, k, None) for k in changes})
        await log_action(
            db=db, tenant_id=auth.tenant_id, entity="products", entity_id=product_id,
            action="UPDATE", old_values=old_snapshot,
            new_values=jsonable_encoder(changes),
            performed_by={"type": "user", "id": auth.user_id},
            ip_address=request.client.host if request.client else None,
        )
    return updated


@router.delete(
    "/{product_id}",
    status_code=204,
    summary="Desactivar producto (soft delete)",
    description="Marca el producto como inactivo (`is_active=false`). No elimina el historial ni los saldos.",
    responses={
        204: {"description": "Producto desactivado"},
        404: {"description": "Producto no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def remove_product(
    product_id: str,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await deactivate_product(product_id, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="products", entity_id=product_id,
        action="DELETE", new_values={"is_active": False},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )


# ── UOM sub-resource ──────────────────────────────────────────────────────────

@router.get(
    "/{product_id}/uom",
    response_model=list[ProductUomResponse],
    summary="Listar unidades de medida del producto",
    description="Retorna las conversiones de unidad configuradas para el producto (ej. CAJA → 12 UNIT).",
    responses={
        404: {"description": "Producto no encontrado"},
        401: {"description": "No autenticado"},
    },
)
async def get_uoms(
    product_id: str,
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_uoms(product_id, db, auth.tenant_id)


@router.post(
    "/{product_id}/uom",
    response_model=ProductUomResponse,
    status_code=201,
    summary="Agregar conversión de unidad",
    description=(
        "Agrega una conversión de unidad al producto. "
        "El `conversion_factor` define cuántas unidades base equivale la nueva UOM "
        "(ej. CAJA con factor 12 = 12 UNIT)."
    ),
    responses={
        201: {"description": "Conversión creada"},
        409: {"description": "UOM duplicada para este producto"},
        404: {"description": "Producto no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_uom(
    product_id: str,
    body: ProductUomCreate,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await add_uom(product_id, body, db, auth.tenant_id)


@router.delete(
    "/{product_id}/uom/{uom_id}",
    status_code=204,
    summary="Eliminar conversión de unidad",
    description="Elimina una conversión de unidad del producto.",
    responses={
        204: {"description": "Conversión eliminada"},
        404: {"description": "Conversión no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def remove_uom(
    product_id: str,
    uom_id: str,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await delete_uom(product_id, uom_id, db, auth.tenant_id)
