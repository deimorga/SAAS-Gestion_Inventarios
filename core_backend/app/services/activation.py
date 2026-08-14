import logging
import secrets
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.activation import ActivationResponse, ChangePasswordResponse

logger = logging.getLogger(__name__)

_ACTIVATION_PREFIX = "activation:"


async def generate_activation_token(user_id: str, redis: aioredis.Redis) -> str:
    """Genera y almacena un token de activación Redis (TTL configurable). Retorna el token."""
    token = secrets.token_urlsafe(32)
    ttl_seconds = settings.ACTIVATION_TOKEN_TTL_HOURS * 3600
    await redis.setex(f"{_ACTIVATION_PREFIX}{token}", ttl_seconds, user_id)
    return token


def activation_url(token: str) -> str:
    return f"{settings.ACTIVATION_BASE_URL.rstrip('/')}/activate?token={token}"


def dispatch_activation_email(
    to_email: str,
    full_name: str,
    token: str,
    template: str = "account_activation",
) -> bool:
    """Encola el email con el enlace de activación. Retorna si se pudo encolar.

    El import de `app.tasks` es diferido para no arrastrar Celery a los módulos
    que solo necesitan generar el token.
    """
    from app.tasks import send_email

    try:
        send_email.delay(
            to_email=to_email,
            template=template,
            context={"full_name": full_name, "activation_url": activation_url(token)},
        )
        return True
    except Exception:
        logger.exception("No se pudo encolar el email de activación para %s", to_email)
        return False


async def activate_account(
    token: str,
    new_password: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> ActivationResponse:
    key = f"{_ACTIVATION_PREFIX}{token}"
    user_id = await redis.get(key)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Token de activación inválido o expirado",
        )

    # Single-use: eliminar el token antes de procesar para evitar replay
    await redis.delete(key)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    user.password_hash = hash_password(new_password)
    user.is_active = True
    user.must_change_password = False
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return ActivationResponse()


async def resend_activation(
    user_id: str,
    requesting_tenant_id: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> str:
    """Genera un nuevo token de activación y lo envía por email. Retorna el token.

    Verifica que el usuario pertenece al tenant solicitante.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or user.tenant_id != requesting_tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if user.is_active and not user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cuenta ya está activada",
        )

    token = await generate_activation_token(user.id, redis)

    if not dispatch_activation_email(
        to_email=user.email,
        full_name=user.full_name,
        token=token,
        template="activation_resent",
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo encolar el email de activación",
        )

    return token


async def change_password(
    user_id: str,
    current_password: str,
    new_password: str,
    db: AsyncSession,
) -> ChangePasswordResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña actual incorrecta",
        )

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    await db.commit()

    return ChangePasswordResponse()
