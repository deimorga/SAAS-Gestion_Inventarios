import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.redis_client import get_redis
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RefreshResponse, TokenResponse
from app.services.auth import authenticate_user, issue_tokens, logout, refresh_session

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Autentica al usuario con email y contraseña. "
        "Retorna un `access_token` (JWT, 30 min) y un `refresh_token` (7 días). "
        "El `access_token` debe enviarse como `Authorization: Bearer <token>` en cada request."
    ),
    responses={
        401: {"description": "Credenciales inválidas"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    user = await authenticate_user(body.email, body.password, db)
    return await issue_tokens(user, redis)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Renovar access token",
    description=(
        "Intercambia un `refresh_token` válido por un nuevo `access_token`. "
        "El refresh token se rota en cada llamada (rotación única)."
    ),
    responses={
        401: {"description": "Refresh token inválido o expirado"},
    },
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await refresh_session(body.refresh_token, db, redis)


@router.post(
    "/logout",
    status_code=204,
    summary="Cerrar sesión",
    description="Invalida el `refresh_token` en Redis. El `access_token` expira naturalmente.",
    responses={204: {"description": "Sesión cerrada exitosamente"}},
)
async def do_logout(
    body: LogoutRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    await logout(body.refresh_token, redis)
