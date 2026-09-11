"""`/v1/platform/*` — aprovisionamiento de tenants por una plataforma externa.

Credencial: API key del tenant interno de MicroNuba con scope `PLATFORM`
(`require_platform`). Esa key no puede leer ni escribir datos de ningún tenant;
solo crea, consulta y da de baja los tenants que ella misma aprovisionó.
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, require_platform
from app.core.redis_client import get_redis
from app.schemas.platform import (
    PlatformTenantCreate,
    PlatformTenantCreated,
    PlatformTenantDeactivated,
    PlatformTenantInfo,
)
from app.services import platform as platform_service

router = APIRouter(prefix="/platform", tags=["Platform"])


@router.post(
    "/tenants",
    response_model=PlatformTenantCreated,
    status_code=201,
    summary="Aprovisionar una sede: tenant + almacén + API key",
    description=(
        "Crea en una sola llamada todo lo que una sede necesita para operar su inventario "
        "aislado del taller principal:\n\n"
        "1. El **tenant** (catálogo y stock propios, aislados por RLS) con su usuario "
        "`tenant_admin`, que recibe el email de activación.\n"
        "2. El **almacén físico** inicial con sus zonas `RECEIVING`, `DISPATCH` y `QUARANTINE`.\n"
        "3. La **API key** de la sede, con los scopes de operación (nunca `ADMIN` ni `PLATFORM`).\n\n"
        "`key_secret` se devuelve **una sola vez**: guardarlo cifrado.\n\n"
        "`external_id` es único por `external_provider`: un reintento con el mismo id "
        "devuelve 409 con el `tenant_id` existente en el `detail`, nunca un duplicado.\n\n"
        "`admin_email` debe ser distinto al de cualquier otro tenant: el login de "
        "Inventarios localiza al usuario por correo, sin tenant."
    ),
    responses={
        201: {"description": "Sede aprovisionada"},
        403: {"description": "La credencial no es una API key de plataforma"},
        404: {"description": "`parent_tenant_id` no existe"},
        409: {"description": "`external_id` ya aprovisionado, o `admin_email` ya registrado"},
        422: {"description": "Datos inválidos (p. ej. scopes ADMIN/PLATFORM en la key de la sede)"},
    },
)
async def create_platform_tenant(
    body: PlatformTenantCreate,
    auth: AuthContext = Depends(require_platform),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await platform_service.provision_tenant(body, platform_key_id=auth.user_id, redis=redis)


@router.get(
    "/tenants/by-external/{provider}/{external_id}",
    response_model=PlatformTenantInfo,
    summary="Buscar una sede por su id en la plataforma",
    description="Útil tras un 409 en el alta, o para verificar si una sede ya está conectada.",
    responses={404: {"description": "No hay tenant con ese id externo"}},
)
async def get_platform_tenant_by_external(
    provider: str,
    external_id: str,
    _auth: AuthContext = Depends(require_platform),
):
    return await platform_service.get_tenant_by_external(provider, external_id)


@router.get(
    "/tenants/{tenant_id}",
    response_model=PlatformTenantInfo,
    summary="Consultar una sede aprovisionada",
    description="Solo tenants creados por una plataforma; los demás responden 404.",
    responses={404: {"description": "Tenant no encontrado o no aprovisionado por plataforma"}},
)
async def get_platform_tenant(
    tenant_id: str,
    _auth: AuthContext = Depends(require_platform),
):
    return await platform_service.get_tenant_info(tenant_id)


@router.delete(
    "/tenants/{tenant_id}",
    response_model=PlatformTenantDeactivated,
    summary="Dar de baja una sede",
    description=(
        "Baja **lógica**: el tenant queda suspendido (sus usuarios no pueden entrar) y todas "
        "sus API keys se revocan, así la key guardada en la plataforma deja de funcionar. "
        "El inventario no se borra; un super_admin puede reactivar el tenant desde el panel."
    ),
    responses={404: {"description": "Tenant no encontrado o no aprovisionado por plataforma"}},
)
async def deactivate_platform_tenant(
    tenant_id: str,
    auth: AuthContext = Depends(require_platform),
):
    return await platform_service.deactivate_tenant(tenant_id, platform_key_id=auth.user_id)
