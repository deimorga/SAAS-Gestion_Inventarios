"""Gestión de super_admins desde el portal (RF-049). Solo `super_admin`.

El bootstrap (`POST /admin/auth/register`) queda para el primero de cada ambiente, que es su
cuenta raíz protegida (L-1). Los demás se crean aquí y NO son cuenta raíz.
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request

from app.api.admin.endpoints.admin_users import _tenant_session
from app.api.deps import AuthContext, require_super_admin
from app.core.config import MICRONUBA_TENANT_ID
from app.core.redis_client import get_redis
from app.schemas.user_management import MessageResponse, SuperAdminCreate, SuperAdminUpdate, UserResponse
from app.services import super_admins as service
from app.services.login_throttle import client_ip
from app.services.user_management import Actor

router = APIRouter(prefix="/super-admins", tags=["Admin — Super admins"])


async def _actor(auth: AuthContext, request: Request) -> Actor:
    return Actor(user_id=auth.user_id, role="super_admin", ip=await client_ip(request))


@router.get(
    "",
    response_model=list[UserResponse],
    summary="Listar super_admins",
    description="Todos los super_admins con su estado. La cuenta raíz viene con `is_protected: true`.",
)
async def list_super_admins(_auth: AuthContext = Depends(require_super_admin)):
    session = await _tenant_session(MICRONUBA_TENANT_ID)
    async with session:
        return await service.list_super_admins(session)


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    summary="Crear un super_admin",
    description=(
        "Crea un super_admin en el tenant interno, pendiente de activación, y le envía el email. "
        "No es cuenta raíz: proteger otra cuenta no se hace desde la aplicación."
    ),
    responses={201: {"description": "Super admin creado"}, 409: {"description": "Email ya registrado"}},
)
async def create_super_admin(
    body: SuperAdminCreate,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
):
    session = await _tenant_session(MICRONUBA_TENANT_ID)
    async with session:
        return await service.create_super_admin(body, await _actor(auth, request), session, redis)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Editar o desactivar un super_admin",
    description=(
        "Cambia el nombre o el estado. Desactivar cierra sus sesiones al momento. "
        "No se puede desactivar a uno mismo ni dejar el sistema sin super_admin activo, y la cuenta "
        "raíz no admite ningún cambio."
    ),
    responses={
        403: {"description": "Cuenta raíz protegida, o intento de desactivarse a uno mismo"},
        404: {"description": "Super admin no encontrado"},
        409: {"description": "Dejaría el sistema sin super_admin activo"},
    },
)
async def update_super_admin(
    user_id: str,
    body: SuperAdminUpdate,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
):
    session = await _tenant_session(MICRONUBA_TENANT_ID)
    async with session:
        return await service.update_super_admin(user_id, body, await _actor(auth, request), session, redis)


@router.post(
    "/{user_id}/password-reset",
    response_model=MessageResponse,
    status_code=202,
    summary="Forzar el reseteo de contraseña de un super_admin",
    description=(
        "Envía el email de reseteo y cierra sus sesiones. Nunca se ve ni se fija la contraseña. "
        "No aplica a la cuenta raíz: su dueño usa «olvidé mi contraseña»."
    ),
    responses={
        403: {"description": "Cuenta raíz protegida"},
        404: {"description": "Super admin no encontrado"},
        409: {"description": "Pendiente de activación o desactivado"},
    },
)
async def super_admin_password_reset(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(require_super_admin),
    redis: aioredis.Redis = Depends(get_redis),
):
    session = await _tenant_session(MICRONUBA_TENANT_ID)
    async with session:
        await service.force_super_admin_reset(user_id, await _actor(auth, request), session, redis)
    return MessageResponse(message="Email de reseteo enviado")
