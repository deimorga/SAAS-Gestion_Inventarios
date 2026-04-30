import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_roles
from app.core.redis_client import get_redis
from app.schemas.user_management import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services.user_management import create_user, list_users, update_user

router = APIRouter(prefix="/users", tags=["Usuarios"])

require_tenant_admin = require_roles("tenant_admin")


@router.get(
    "",
    response_model=UserListResponse,
    summary="Listar usuarios del tenant",
    description=(
        "Retorna todos los usuarios del tenant autenticado con paginación. "
        "Solo accesible para `tenant_admin`."
    ),
    responses={200: {"description": "Lista de usuarios"}},
)
async def list_tenant_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_users(auth.tenant_id, db, page, size)


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    summary="Crear usuario en el tenant",
    description=(
        "Crea un nuevo usuario en el tenant del `tenant_admin` autenticado. "
        "El rol solo puede ser `api_consumer`, `inventory_manager` o `viewer` "
        "(D-04: no se pueden escalar privilegios). "
        "El usuario se crea inactivo y debe activar su cuenta via `/auth/activate`."
    ),
    responses={
        201: {"description": "Usuario creado"},
        403: {"description": "Rol no permitido para tenant_admin"},
        409: {"description": "Email ya registrado"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def create_tenant_user(
    body: UserCreate,
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await create_user(body, auth.tenant_id, auth.user_id, db, redis)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Actualizar usuario",
    description=(
        "Permite al `tenant_admin` actualizar el nombre o estado de un usuario de su tenant. "
        "No permite cambiar email ni rol."
    ),
    responses={
        200: {"description": "Usuario actualizado"},
        404: {"description": "Usuario no encontrado en este tenant"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def patch_user(
    user_id: str,
    body: UserUpdate,
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await update_user(user_id, auth.tenant_id, body, db)
