import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_admin_db, require_super_admin
from app.core.redis_client import get_redis
from app.schemas.admin_tenant import (
    TenantCreate,
    TenantCreateResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services.admin_tenant import (
    create_tenant,
    get_tenant,
    list_tenants,
    update_tenant,
)
from app.services.api_key_rotation import admin_list_tenant_api_keys, admin_revoke_api_key



router = APIRouter(prefix="/tenants", tags=["Admin — Tenants"])


@router.post(
    "",
    response_model=TenantCreateResponse,
    status_code=201,
    summary="Crear tenant y administrador inicial",
    description=(
        "Crea un nuevo tenant en la plataforma junto con su primer usuario `tenant_admin`. "
        "El administrador se crea con `is_active=False` y `must_change_password=True`. "
        "Se genera un token de activación en Redis (TTL 48h) que será enviado por email "
        "cuando el módulo de notificaciones esté activo (F-7). "
        "El slug se genera automáticamente desde el nombre si no se provee."
    ),
    responses={
        201: {"description": "Tenant y administrador creados"},
        409: {"description": "Slug ya en uso o email de administrador duplicado"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def create_new_tenant(
    body: TenantCreate,
    auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await create_tenant(body, auth.user_id, db, redis)


@router.get(
    "",
    response_model=TenantListResponse,
    summary="Listar todos los tenants",
    description="Retorna todos los tenants registrados en la plataforma con paginación.",
    responses={200: {"description": "Lista paginada de tenants"}},
)
async def list_all_tenants(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    return await list_tenants(db, page, size)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Obtener tenant por ID",
    description="Retorna los detalles de un tenant específico.",
    responses={
        200: {"description": "Datos del tenant"},
        404: {"description": "Tenant no encontrado"},
    },
)
async def get_one_tenant(
    tenant_id: str,
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    return await get_tenant(tenant_id, db)


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Actualizar tenant",
    description=(
        "Permite actualizar el nombre, estado (`is_active`) o tier de suscripción de un tenant. "
        "Suspender un tenant (`is_active=False`) impide que sus usuarios inicien sesión "
        "pero no revoca las API Keys activas."
    ),
    responses={
        200: {"description": "Tenant actualizado"},
        404: {"description": "Tenant no encontrado"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def patch_tenant(
    tenant_id: str,
    body: TenantUpdate,
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    return await update_tenant(tenant_id, body, db)


@router.get(
    "/{tenant_id}/api-keys",
    response_model=PaginatedResponse,
    summary="Listar API Keys de un tenant (admin)",
    description="Retorna todas las API Keys del tenant especificado. Solo accesible por super_admin.",
    responses={
        200: {"description": "Lista paginada de API Keys"},
        404: {"description": "Tenant no encontrado"},
    },
)
async def list_tenant_api_keys(
    tenant_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None, description="Filtrar por estado activo/inactivo"),
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    return await admin_list_tenant_api_keys(tenant_id, db, page, size, is_active)


@router.delete(
    "/{tenant_id}/api-keys/{key_id}",
    status_code=204,
    summary="Revocar API Key de un tenant (admin)",
    description="Desactiva permanentemente la API Key indicada. Solo accesible por super_admin.",
    responses={
        204: {"description": "API Key revocada"},
        404: {"description": "Tenant o API Key no encontrados"},
    },
)
async def revoke_tenant_api_key(
    tenant_id: str,
    key_id: str,
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    await admin_revoke_api_key(tenant_id, key_id, db)
