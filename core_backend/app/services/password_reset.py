"""Recuperación de contraseña por email (RF-050).

Es también el mecanismo del «forzar reseteo» de RF-047, RF-048 y RF-049: el administrador
nunca conoce ni fija la contraseña de otro usuario (L-5), solo dispara este email.

Claves en Redis:
  pwd_reset:<token>          → user_id          TTL 60 min, un solo uso
  pwd_reset_user:<user_id>   → último token     TTL 60 min; pedir un enlace nuevo invalida el anterior
  pwd_forgot:email:<email>   contador           3 solicitudes por email y hora
  pwd_forgot:ip:<ip>         contador           10 solicitudes por IP y hora
"""
import logging
import secrets

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.services.activation import dispatch_activation_email, generate_activation_token
from app.services.audit import log_action
from app.services.login_throttle import clear_account_failures
from app.services.sessions import revoke_all_sessions

logger = logging.getLogger(__name__)

RESET_TTL_SECONDS = 60 * 60
FORGOT_WINDOW_SECONDS = 60 * 60
FORGOT_MAX_PER_EMAIL = 3
FORGOT_MAX_PER_IP = 10

# La misma respuesta exista o no el email, esté activo o no (RN-050-1)
PUBLIC_MESSAGE = "Si el email está registrado, recibirás un enlace en unos minutos."
INVALID_LINK = "El enlace no es válido o caducó."


def _reset_key(token: str) -> str:
    return f"pwd_reset:{token}"


def _reset_user_key(user_id: str) -> str:
    return f"pwd_reset_user:{user_id}"


def reset_url(token: str) -> str:
    return f"{settings.ACTIVATION_BASE_URL.rstrip('/')}/reset-password?token={token}"


async def issue_reset_token(user_id: str, redis: aioredis.Redis) -> str:
    """Genera el token e invalida el anterior del mismo usuario (RN-050-4)."""
    previous = await redis.get(_reset_user_key(user_id))
    if previous:
        await redis.delete(_reset_key(previous))
    token = secrets.token_urlsafe(32)
    await redis.setex(_reset_key(token), RESET_TTL_SECONDS, user_id)
    await redis.setex(_reset_user_key(user_id), RESET_TTL_SECONDS, token)
    return token


def dispatch_reset_email(to_email: str, full_name: str, token: str) -> bool:
    """Encola el email de reseteo. Devuelve si se pudo encolar."""
    from app.tasks import send_email  # diferido: no arrastrar Celery a quien solo genera el token

    try:
        send_email.delay(
            to_email=to_email,
            template="password_reset",
            context={
                "full_name": full_name,
                "reset_url": reset_url(token),
                "ttl_minutes": RESET_TTL_SECONDS // 60,
            },
        )
        return True
    except Exception:
        logger.exception("No se pudo encolar el email de reseteo para %s", to_email)
        return False


async def _count(redis: aioredis.Redis, key: str) -> tuple[int, int]:
    """Incrementa un contador de ventana fija. Devuelve (valor, segundos restantes)."""
    value = await redis.incr(key)
    if value == 1:
        await redis.expire(key, FORGOT_WINDOW_SECONDS)
    ttl = await redis.ttl(key)
    return value, ttl if ttl > 0 else FORGOT_WINDOW_SECONDS


async def _enforce_forgot_limits(email: str, ip: str, redis: aioredis.Redis) -> None:
    """3 por email y hora, 10 por IP y hora (RN-050-5). Es el único caso que no responde 202."""
    for key, limit in ((f"pwd_forgot:email:{email}", FORGOT_MAX_PER_EMAIL), (f"pwd_forgot:ip:{ip}", FORGOT_MAX_PER_IP)):
        value, ttl = await _count(redis, key)
        if value > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Inténtalo de nuevo más tarde.",
                headers={"Retry-After": str(ttl)},
            )


async def request_reset(email: str, ip: str, db: AsyncSession, redis: aioredis.Redis) -> None:
    """Procesa «olvidé mi contraseña». No revela nada sobre si el email existe (RN-050-1).

    `db` es una sesión de sistema (`get_db`): debe localizar al usuario antes de saber su tenant.
    Los endpoints que la usan nunca devuelven datos de un tenant.
    """
    email = email.strip().lower()
    await _enforce_forgot_limits(email, ip, redis)

    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    if user is None:
        return
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    if tenant is None or not tenant.is_active:
        return  # tenant suspendido: no se envía nada (RN-050-3)

    if user.is_active:
        token = await issue_reset_token(user.id, redis)
        dispatch_reset_email(user.email, user.full_name, token)
    elif user.must_change_password:
        # Pendiente de activación: no hay contraseña que recuperar, se reenvía la activación (RN-050-2)
        token = await generate_activation_token(user.id, redis)
        dispatch_activation_email(user.email, user.full_name, token, template="activation_resent")
    # Desactivado: no se envía nada (RN-050-3)


async def reset_password(
    token: str,
    new_password: str,
    ip: str | None,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """Fija la contraseña nueva con el token, cierra todas las sesiones y avisa por email."""
    user_id = await redis.get(_reset_key(token))
    if not user_id or await redis.get(_reset_user_key(user_id)) != token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LINK)

    # Un solo uso: se consume antes de procesar para impedir un replay
    await redis.delete(_reset_key(token), _reset_user_key(user_id))

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LINK)
    tenant = (await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    if tenant is None or not tenant.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_LINK)

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    # `log_action` confirma el cambio de contraseña junto con la auditoría. Nunca se anota la
    # contraseña ni el token.
    await log_action(
        db,
        tenant_id=user.tenant_id,
        entity="users",
        entity_id=user.id,
        action="PASSWORD_RESET",
        new_values={},
        performed_by={"type": "user", "id": user.id, "role": user.role},
        ip_address=ip,
    )

    await revoke_all_sessions(user.id, redis)  # RF-051
    await clear_account_failures(redis, user.email)  # si estaba bloqueado por intentos, entra de inmediato

    from app.tasks import send_email

    try:
        send_email.delay(
            to_email=user.email,
            template="password_changed",
            context={"full_name": user.full_name},
        )
    except Exception:
        logger.exception("No se pudo encolar el aviso de contraseña cambiada para %s", user.email)
