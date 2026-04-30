import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.redis_client import get_redis
from app.schemas.admin_auth import AdminLoginResponse, AdminRegisterRequest
from app.schemas.auth import LoginRequest
from app.services.admin_auth import login_super_admin, register_super_admin

router = APIRouter(prefix="/auth", tags=["Admin — Auth"])


@router.post(
    "/register",
    response_model=AdminLoginResponse,
    status_code=201,
    summary="Bootstrap de super_admin",
    description=(
        "Crea el primer `super_admin` de la plataforma. "
        "Solo puede ejecutarse **una vez**: si ya existe un super_admin, retorna 409. "
        "Requiere el header `X-Bootstrap-Secret` con el valor configurado en `ADMIN_BOOTSTRAP_SECRET`. "
        "Si esa variable no está configurada en el entorno, retorna 503 "
        "(el bootstrap está deshabilitado en producción tras el alta inicial)."
    ),
    responses={
        201: {"description": "Super admin creado y sesión iniciada"},
        403: {"description": "Secret inválido"},
        409: {"description": "Ya existe un super_admin o el email está en uso"},
        422: {"description": "Datos de entrada inválidos"},
        503: {"description": "Bootstrap deshabilitado (ADMIN_BOOTSTRAP_SECRET no configurado)"},
    },
)
async def bootstrap_register(
    body: AdminRegisterRequest,
    x_bootstrap_secret: str = Header(..., alias="X-Bootstrap-Secret"),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await register_super_admin(body, x_bootstrap_secret, db, redis)


@router.post(
    "/login",
    response_model=AdminLoginResponse,
    summary="Login de super_admin",
    description=(
        "Autentica exclusivamente a usuarios con rol `super_admin`. "
        "Superficie separada de `/v1/auth/login` para no revelar la existencia del panel de administración "
        "a usuarios de cliente. "
        "Si las credenciales son válidas pero el rol no es `super_admin`, retorna 403 genérico."
    ),
    responses={
        200: {"description": "Login exitoso"},
        401: {"description": "Credenciales inválidas"},
        403: {"description": "Rol no permitido en esta superficie o cuenta suspendida"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def admin_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await login_super_admin(body.email, body.password, db, redis)
