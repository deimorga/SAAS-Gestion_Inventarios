import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, get_current_auth, get_db, require_roles
from app.core.redis_client import get_redis
from app.schemas.activation import (
    ActivateRequest,
    ActivationResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
)
from app.services.activation import activate_account, change_password, resend_activation

router = APIRouter(prefix="/auth", tags=["Auth — Activación"])

require_tenant_admin = require_roles("tenant_admin")


@router.post(
    "/activate",
    response_model=ActivationResponse,
    summary="Activar cuenta con token",
    description=(
        "Activa la cuenta de un usuario usando el token de un solo uso enviado por email (TTL 48h). "
        "El token se elimina al usarse — un segundo intento retorna 410. "
        "No requiere autenticación: el token es la credencial."
    ),
    responses={
        200: {"description": "Cuenta activada"},
        410: {"description": "Token inválido, ya usado o expirado"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def activate(
    body: ActivateRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await activate_account(body.token, body.password, db, redis)


@router.post(
    "/resend-activation/{user_id}",
    response_model=ActivationResponse,
    summary="Reenviar activación",
    description=(
        "Genera un nuevo token de activación para el usuario indicado. "
        "Solo puede ser invocado por un `tenant_admin` del mismo tenant. "
        "El token anterior no se invalida — expira naturalmente al cabo de 48h."
    ),
    responses={
        200: {"description": "Token de activación regenerado"},
        404: {"description": "Usuario no encontrado o no pertenece al tenant"},
        409: {"description": "La cuenta ya está activada"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def resend(
    user_id: str,
    auth: AuthContext = Depends(require_tenant_admin),
    db: AsyncSession = Depends(get_auth_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await resend_activation(user_id, auth.tenant_id, db, redis)
    return ActivationResponse(message="Token de activación regenerado")


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Cambiar contraseña",
    description=(
        "Permite a cualquier usuario autenticado cambiar su contraseña. "
        "Requiere la contraseña actual para confirmación. "
        "Limpia el flag `must_change_password` tras el cambio exitoso."
    ),
    responses={
        200: {"description": "Contraseña actualizada"},
        401: {"description": "Contraseña actual incorrecta"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
async def do_change_password(
    body: ChangePasswordRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_auth_db),
):
    return await change_password(auth.user_id, body.current_password, body.new_password, db)
