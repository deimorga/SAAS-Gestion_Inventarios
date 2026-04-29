from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_db, require_catalog_read, require_catalog_write
from app.schemas.supplier import (
    SupplierCreate,
    SupplierProductCreate,
    SupplierProductResponse,
    SupplierProductUpdate,
    SupplierResponse,
    SupplierUpdate,
)
from app.services import supplier as svc
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=201,
    summary="Crear proveedor",
    description=(
        "Registra un nuevo proveedor en el directorio del tenant. "
        "El `code` debe ser único dentro del tenant y solo puede contener letras, números, guiones y guiones bajos."
    ),
    responses={
        201: {"description": "Proveedor creado"},
        409: {"description": "Código de proveedor duplicado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_supplier(
    body: SupplierCreate,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.create_supplier(body, db, auth.tenant_id)


@router.get(
    "",
    response_model=list[SupplierResponse],
    summary="Listar proveedores",
    description="Retorna todos los proveedores del tenant. Por defecto solo los activos.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def list_suppliers(
    is_active: bool = Query(True, description="Filtrar por estado activo"),
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.list_suppliers(db, auth.tenant_id, is_active)


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Obtener proveedor por ID",
    description="Retorna el detalle completo de un proveedor.",
    responses={
        404: {"description": "Proveedor no encontrado"},
        401: {"description": "No autenticado"},
    },
)
async def get_supplier(
    supplier_id: str,
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.get_supplier(supplier_id, db, auth.tenant_id)


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
    summary="Actualizar proveedor",
    description="Actualiza parcialmente los datos del proveedor. Solo los campos enviados se modifican.",
    responses={
        404: {"description": "Proveedor no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def update_supplier(
    supplier_id: str,
    body: SupplierUpdate,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.update_supplier(supplier_id, body, db, auth.tenant_id)


@router.delete(
    "/{supplier_id}",
    status_code=204,
    summary="Desactivar proveedor (soft delete)",
    description="Marca el proveedor como inactivo. No elimina las asociaciones ni el historial.",
    responses={
        204: {"description": "Proveedor desactivado"},
        404: {"description": "Proveedor no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def deactivate_supplier(
    supplier_id: str,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await svc.deactivate_supplier(supplier_id, db, auth.tenant_id)


# ── Sub-recurso: SupplierProduct (RF-012) ─────────────────────────────────────

@router.post(
    "/{supplier_id}/products",
    response_model=SupplierProductResponse,
    status_code=201,
    summary="Asociar producto al proveedor con costo de reposición",
    description=(
        "Vincula un producto al proveedor con su costo unitario de compra, tiempo de entrega y cantidad mínima de pedido (MOQ). "
        "Permite marcar un proveedor como preferido para el producto. "
        "Un mismo producto no puede asociarse dos veces al mismo proveedor."
    ),
    responses={
        201: {"description": "Asociación creada"},
        404: {"description": "Proveedor o producto no encontrado"},
        409: {"description": "El producto ya está asociado a este proveedor"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def add_product_to_supplier(
    supplier_id: str,
    body: SupplierProductCreate,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.add_supplier_product(supplier_id, body, db, auth.tenant_id)


@router.get(
    "/{supplier_id}/products",
    response_model=list[SupplierProductResponse],
    summary="Listar productos del proveedor",
    description="Retorna los productos asociados al proveedor con sus costos y parámetros de reposición.",
    responses={
        404: {"description": "Proveedor no encontrado"},
        401: {"description": "No autenticado"},
    },
)
async def list_products_by_supplier(
    supplier_id: str,
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.list_supplier_products(supplier_id, db, auth.tenant_id)


@router.patch(
    "/{supplier_id}/products/{sp_id}",
    response_model=SupplierProductResponse,
    summary="Actualizar costo de reposición",
    description="Actualiza el costo unitario, lead time, MOQ o preferencia del proveedor para un producto.",
    responses={
        404: {"description": "Asociación no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def update_supplier_product(
    supplier_id: str,
    sp_id: str,
    body: SupplierProductUpdate,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.update_supplier_product(supplier_id, sp_id, body, db, auth.tenant_id)


@router.delete(
    "/{supplier_id}/products/{sp_id}",
    status_code=204,
    summary="Eliminar asociación proveedor-producto",
    description="Elimina la asociación de costo de reposición entre el proveedor y el producto.",
    responses={
        204: {"description": "Asociación eliminada"},
        404: {"description": "Asociación no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def delete_supplier_product(
    supplier_id: str,
    sp_id: str,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await svc.delete_supplier_product(supplier_id, sp_id, db, auth.tenant_id)
