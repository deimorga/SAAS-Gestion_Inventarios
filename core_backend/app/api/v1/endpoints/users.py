import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_roles
from app.core.redis_client import get_redis
from app.schemas.user_management import (
    MessageResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services import user_management as users
from app.services.login_throttle import client_ip
from app.services.user_management import Actor

router = APIRouter(prefix="/users", tags=["Usuarios"])

require_tenant_admin = require_roles("tenant_admin")


async def _actor(auth: AuthContext, request: Request) -> Actor:
    return Actor(
        user_id=auth.user_id,
        role="tenant_admin",
        ip=await client_ip(request),
        kind="api_key" if auth.auth_type == "api_key" else "user",
    )


@router.get(
    "",
    response_model=UserListResponse,
    summary="Listar usuarios del tenant",
    description=(
        "Usuarios del tenant autenticado, con paginación. Filtra por `status` "
        "(`active`, `pending`, `disabled`) y busca por email o nombre con `q`. "
        "Solo accesible para `tenant_admin`."
    ),
    responses={200: {"description": "Lista de usuarios"}},
)
async def list_tenant_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(active|pending|disabled)$"),
    q: str | None = Query(None, max_length=100),
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await users.list_users(auth.tenant_id, db, page, size, status_filter=status, q=q)


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    summary="Crear usuario en el tenant",
    description=(
        "Crea un usuario en el tenant del `tenant_admin` autenticado. El rol solo puede ser "
        "`inventory_manager` o `viewer` (por defecto `viewer`): un tenant_admin no crea otros "
        "tenant_admin (eso lo hace el super_admin). El email es único en toda la plataforma. "
        "El usuario se crea pendiente y recibe el email de activación."
    ),
    responses={
        201: {"description": "Usuario creado"},
        403: {"description": "Rol no permitido para tenant_admin"},
        409: {"description": "Email ya registrado en cualquier tenant"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def create_tenant_user(
    body: UserCreate,
    request: Request,
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await users.create_user(body, auth.tenant_id, await _actor(auth, request), db, redis)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario",
    description=(
        "Cambia nombre, rol (`inventory_manager` o `viewer`) o estado. Desactivar cierra las "
        "sesiones del usuario al momento. No se puede tocar a otro `tenant_admin` ni desactivarse "
        "a uno mismo, y un usuario pendiente solo se activa con su enlace. El email no se edita."
    ),
    responses={
        200: {"description": "Usuario actualizado"},
        403: {"description": "Acción no permitida (otro tenant_admin, uno mismo o cuenta protegida)"},
        404: {"description": "Usuario no encontrado en este tenant"},
        409: {"description": "Activar a mano un usuario pendiente"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def patch_user(
    user_id: str,
    body: UserUpdate,
    request: Request,
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await users.update_user(user_id, auth.tenant_id, body, await _actor(auth, request), db, redis)


@router.post(
    "/{user_id}/password-reset",
    response_model=MessageResponse,
    status_code=202,
    summary="Forzar el reseteo de contraseña de un usuario",
    description=(
        "Envía al usuario el email de reseteo y cierra sus sesiones. El administrador nunca ve ni "
        "fija la contraseña. Solo para usuarios activos."
    ),
    responses={
        202: {"description": "Email de reseteo enviado"},
        403: {"description": "Acción no permitida"},
        404: {"description": "Usuario no encontrado en este tenant"},
        409: {"description": "Usuario pendiente de activación o desactivado"},
    },
)
async def force_password_reset(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await users.request_password_reset_for(user_id, auth.tenant_id, await _actor(auth, request), db, redis)
    return MessageResponse(message="Email de reseteo enviado")
