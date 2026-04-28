from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_catalog_read, require_catalog_write
from app.schemas.catalog import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.audit import log_action
from app.services.category import create_category, delete_category, get_category, list_categories, update_category

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "",
    response_model=list,
    summary="Listar categorías",
    description=(
        "Retorna el árbol de categorías del tenant. "
        "Con `flat=false` (default) retorna jerarquía anidada; con `flat=true` retorna lista plana. "
        "Con `include_counts=true` agrega el conteo de productos por categoría."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_categories(
    flat: bool = Query(False, description="Retornar lista plana en lugar de árbol anidado"),
    include_counts: bool = Query(False, description="Incluir conteo de productos por categoría"),
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_categories(db, auth.tenant_id, flat, include_counts)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=201,
    summary="Crear categoría",
    description=(
        "Crea una nueva categoría. Si se envía `parent_id`, se crea como sub-categoría. "
        "El `path` se construye automáticamente como jerarquía materializada (ej. `Electronics / Monitors`)."
    ),
    responses={
        201: {"description": "Categoría creada"},
        404: {"description": "Categoría padre no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def add_category(
    body: CategoryCreate,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    cat = await create_category(body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="categories", entity_id=str(cat.id),
        action="CREATE", new_values={"name": cat.name, "path": cat.path},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return cat


@router.get(
    "/{cat_id}",
    response_model=CategoryResponse,
    summary="Obtener categoría por ID",
    description="Retorna el detalle de una categoría incluyendo su path jerárquico completo.",
    responses={
        404: {"description": "Categoría no encontrada"},
        401: {"description": "No autenticado"},
    },
)
async def get_category_detail(
    cat_id: str,
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_category(cat_id, db, auth.tenant_id)


@router.patch(
    "/{cat_id}",
    response_model=CategoryResponse,
    summary="Actualizar categoría",
    description="Actualiza parcialmente el nombre o el padre de una categoría. El path se recalcula automáticamente.",
    responses={
        404: {"description": "Categoría no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def patch_category(
    cat_id: str,
    body: CategoryUpdate,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    updated = await update_category(cat_id, body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="categories", entity_id=cat_id,
        action="UPDATE", new_values=body.model_dump(exclude_none=True),
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete(
    "/{cat_id}",
    status_code=204,
    summary="Eliminar categoría",
    description=(
        "Elimina la categoría. Los productos asociados quedan sin categoría (`category_id = null`). "
        "No se puede eliminar si tiene sub-categorías activas."
    ),
    responses={
        204: {"description": "Categoría eliminada"},
        409: {"description": "La categoría tiene sub-categorías activas"},
        404: {"description": "Categoría no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def remove_category(
    cat_id: str,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await delete_category(cat_id, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="categories", entity_id=cat_id,
        action="DELETE", new_values={"is_active": False},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
