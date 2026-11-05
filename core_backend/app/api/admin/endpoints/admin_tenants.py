from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_admin_db, require_super_admin
from app.core.redis_client import get_redis
from app.core.security import tenant_tier_key
from app.schemas.admin_tenant import (
    TenantCreate,
    TenantCreateResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse
from app.schemas.common import PaginatedResponse
from app.schemas.platform import PANEL_PROVIDER, PlatformTenantCreate, PlatformTenantCreated, SedeCreate
from app.services.admin_tenant import (
    create_tenant,
    get_tenant,
    list_tenants,
    update_tenant,
)
from app.services import platform as platform_service
from app.services.api_key import create_api_key
from app.services.api_key_rotation import admin_list_tenant_api_keys, admin_revoke_api_key
from app.services.audit import log_action


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
    redis: aioredis.Redis = Depends(get_redis),
):
    tenant = await update_tenant(tenant_id, body, db)
    # El rate limit cachea el tier: sin esto el cambio tardaría el TTL en aplicarse
    await redis.delete(tenant_tier_key(tenant_id))
    return tenant


@router.post(
    "/{tenant_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=201,
    summary="Crear API Key de un tenant (admin)",
    description=(
        "Genera una nueva API Key para el tenant indicado. "
        "El secreto solo se expone una vez en la respuesta. "
        "Solo accesible por super_admin."
    ),
    responses={
        201: {"description": "API Key creada."},
        404: {"description": "Tenant no encontrado"},
    },
)
async def create_tenant_api_key(
    tenant_id: str,
    body: ApiKeyCreate,
    auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    await get_tenant(tenant_id, db)
    result = await create_api_key(body, db, tenant_id)
    await log_action(
        db=db,
        tenant_id=tenant_id,
        entity="api_keys",
        entity_id=str(result.id),
        action="CREATE_BY_ADMIN",
        new_values={"name": result.name, "scopes": [s.value for s in result.scopes]},
        performed_by={"type": "user", "id": auth.user_id},
    )
    return result


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


# ── Sedes (tenants hijos) ──────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/sedes",
    response_model=list[TenantResponse],
    summary="Sedes de un tenant",
    description="Tenants cuyo `parent_tenant_id` es este tenant. Cada sede es un tenant aparte, con catálogo y stock propios.",
)
async def list_tenant_sedes(
    tenant_id: str,
    _auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    await get_tenant(tenant_id, db)
    return [TenantResponse.model_validate(t) for t in await platform_service.list_children(tenant_id)]


@router.post(
    "/{tenant_id}/sedes",
    response_model=PlatformTenantCreated,
    status_code=201,
    summary="Crear una sede de un tenant desde el panel",
    description=(
        "Mismo aprovisionamiento que `POST /v1/platform/tenants` (tenant aparte + admin + almacén "
        "físico con zonas + API key), pero pedido por un super_admin desde el panel y con el "
        "tenant padre en la ruta. Sin `external_id` la sede queda como creada desde el panel."
    ),
    responses={
        404: {"description": "Tenant padre no encontrado"},
        409: {"description": "`external_id` ya usado o `admin_email` ya registrado"},
    },
)
async def create_tenant_sede(
    tenant_id: str,
    body: SedeCreate,
    auth: AuthContext = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await get_tenant(tenant_id, db)
    # Con external_id viene de Appits y se registra como tal; sin él, la sede se
    # creó a mano y recibe un id propio para que el índice único siga aplicando.
    if body.external_id:
        provider, external_id = "appits", body.external_id
    else:
        provider, external_id = PANEL_PROVIDER, f"panel-{uuid4().hex[:12]}"
    return await platform_service.provision_tenant(
        PlatformTenantCreate(
            name=body.name,
            tax_id=body.tax_id,
            admin_email=body.admin_email,
            admin_full_name=body.admin_full_name,
            external_provider=provider,
            external_id=external_id,
            parent_tenant_id=tenant_id,
            warehouse=body.warehouse,
            api_key_name=body.api_key_name,
        ),
        performed_by=platform_service.admin_user_performer(auth.user_id),
        redis=redis,
    )
