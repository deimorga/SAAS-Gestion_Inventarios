"""Gestión de usuarios de un tenant desde el portal de super_admin (RF-047).

Existe porque `/v1/users` y `/v1/auth/resend-activation` exigen rol `tenant_admin` y resuelven
el usuario contra el tenant de quien llama: un `super_admin` recibe 403. Sin estos endpoints,
un tenant recién creado cuyo email de bienvenida no llegó queda inaccesible sin tocar la base
de datos.

Todos operan con el RLS del tenant indicado, no con el bypass de super_admin, y comparten el
servicio con `/v1/users`: las reglas de permisos y la auditoría viven en un solo sitio.
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_super_admin
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.core.redis_client import get_redis
from app.models.tenant import Tenant
from app.schemas.activation import ActivationResponse
from app.schemas.user_management import (
    MessageResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services import user_management as user_service
from app.services.login_throttle import client_ip
from app.services.user_management import Actor

router = APIRouter(tags=["Admin — Usuarios"])


async def _tenant_session(tenant_id: str) -> AsyncSession:
    """Sesión con el RLS del tenant indicado, no con el bypass de super_admin.

    Operar bajo las políticas del tenant hace que un `tenant_id` equivocado
    devuelva vacío en lugar de tocar datos de otro cliente.
    """
    session = AsyncSessionLocal()
    await set_tenant_context(session, tenant_id)
    return session


async def _actor(auth: AuthContext, request: Request) -> Actor:
    return Actor(user_id=auth.user_id, role="super_admin", ip=await client_ip(request))


async def _require_tenant(session: AsyncSession, tenant_id: str) -> None:
    # `tenants` no está bajo RLS: se puede consultar desde la sesión del tenant
    if await session.get(Tenant, tenant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant no encontrado")


@router.get(
    "/tenants/{tenant_id}/users",
    response_model=UserListResponse,
    summary="Listar usuarios de un tenant",
    description=(
        "Usuarios del tenant indicado, con su estado (`pending`, `active`, `disabled`). "
        "Filtra con `status` y busca por email o nombre con `q`. Los super_admins no aparecen aquí."
    ),
)
async def admin_list_users(
    tenant_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status", pattern="^(active|pending|disabled)$"),
    q: str | None = Query(None, max_length=100),
    _auth: AuthContext = Depends(require_super_admin),
) -> UserListResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        return await user_service.list_users(
            tenant_id=tenant_id, db=session, page=page, size=size, status_filter=status_filter, q=q
        )


@router.post(
    "/tenants/{tenant_id}/users",
    response_model=UserResponse,
    status_code=201,
    summary="Crear un usuario en un tenant",
    description=(
        "Crea un `tenant_admin`, `inventory_manager` o `viewer` (por defecto `viewer`) pendiente de "
        "activación y le envía el email. Nunca crea super_admins (ver `/admin/super-admins`). "
        "El email es único en toda la plataforma."
    ),
    responses={
        201: {"description": "Usuario creado"},
        404: {"description": "Tenant no encontrado"},
        409: {"description": "Email ya registrado en cualquier tenant"},
    },
)
async def admin_create_user(
    tenant_id: str,
    body: UserCreate,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
) -> UserResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        await _require_tenant(session, tenant_id)
        return await user_service.create_user(body, tenant_id, await _actor(auth, request), session, redis)


@router.patch(
    "/tenants/{tenant_id}/users/{user_id}",
    response_model=UserResponse,
    summary="Editar un usuario de un tenant",
    description=(
        "Cambia nombre, rol o estado. Desactivar cierra las sesiones del usuario al momento. "
        "Un usuario pendiente solo se activa con su enlace. El email no se edita."
    ),
    responses={
        403: {"description": "Cuenta protegida o rol no asignable"},
        404: {"description": "Usuario no encontrado en este tenant"},
        409: {"description": "Activar a mano un usuario pendiente"},
    },
)
async def admin_update_user(
    tenant_id: str,
    user_id: str,
    body: UserUpdate,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
) -> UserResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        return await user_service.update_user(
            user_id, tenant_id, body, await _actor(auth, request), session, redis
        )


@router.post(
    "/tenants/{tenant_id}/users/{user_id}/resend-activation",
    response_model=ActivationResponse,
    summary="Reenviar activación a un usuario de un tenant",
    description=(
        "Genera un nuevo token de activación (TTL 48h) y encola el email. Solo para usuarios "
        "pendientes. El token anterior no se invalida: expira por su cuenta."
    ),
    responses={
        200: {"description": "Token regenerado y email encolado"},
        404: {"description": "Usuario no encontrado o no pertenece al tenant"},
        409: {"description": "La cuenta ya está activada o está desactivada"},
        503: {"description": "No se pudo encolar el email"},
    },
)
async def admin_resend_activation(
    tenant_id: str,
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
) -> ActivationResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        await user_service.resend_activation_for(
            user_id, tenant_id, await _actor(auth, request), session, redis
        )
    return ActivationResponse(message="Email de activación reenviado")


@router.post(
    "/tenants/{tenant_id}/users/{user_id}/password-reset",
    response_model=MessageResponse,
    status_code=202,
    summary="Forzar el reseteo de contraseña de un usuario de un tenant",
    description=(
        "Envía al usuario el email de reseteo y cierra sus sesiones. El super_admin nunca ve ni fija "
        "la contraseña. Solo para usuarios activos."
    ),
    responses={
        202: {"description": "Email de reseteo enviado"},
        403: {"description": "Cuenta protegida"},
        404: {"description": "Usuario no encontrado en este tenant"},
        409: {"description": "Usuario pendiente de activación o desactivado"},
    },
)
async def admin_force_password_reset(
    tenant_id: str,
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
) -> MessageResponse:
    session = await _tenant_session(tenant_id)
    async with session:
        await user_service.request_password_reset_for(
            user_id, tenant_id, await _actor(auth, request), session, redis
        )
    return MessageResponse(message="Email de reseteo enviado")
