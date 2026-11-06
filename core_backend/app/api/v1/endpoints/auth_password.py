"""Recuperación de contraseña (RF-050). Endpoints públicos: el token es la credencial."""
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.redis_client import get_redis
from app.schemas.password_reset import ForgotPasswordRequest, ResetPasswordRequest
from app.schemas.user_management import MessageResponse
from app.services import password_reset
from app.services.login_throttle import client_ip

router = APIRouter(prefix="/auth", tags=["Auth — Recuperación de contraseña"])


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=202,
    summary="Solicitar el enlace para restablecer la contraseña",
    description=(
        "Responde SIEMPRE lo mismo, exista o no el email y esté o no activo: no permite averiguar "
        "qué emails tienen cuenta. Si el usuario está activo recibe un enlace de un solo uso "
        "(60 min); si está pendiente de activación se le reenvía la activación. "
        "Límite: 3 solicitudes por email y hora, y 10 por IP y hora."
    ),
    responses={
        202: {"description": "Solicitud recibida"},
        429: {"description": "Demasiadas solicitudes"},
    },
)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await password_reset.request_reset(body.email, await client_ip(request), db, redis)
    return MessageResponse(message=password_reset.PUBLIC_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Fijar una contraseña nueva con el enlace del email",
    description=(
        "Consume el token (un solo uso), cambia la contraseña, cierra todas las sesiones del "
        "usuario, borra sus intentos fallidos de login y envía un aviso por email."
    ),
    responses={
        200: {"description": "Contraseña actualizada"},
        400: {"description": "Token inválido, usado o caducado"},
        422: {"description": "Contraseña fuera de política (mínimo 12 caracteres)"},
    },
)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await password_reset.reset_password(body.token, body.new_password, await client_ip(request), db, redis)
    return MessageResponse(message="Contraseña actualizada. Ya puedes iniciar sesión.")
