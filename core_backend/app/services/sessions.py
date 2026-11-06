"""Sesiones por usuario y revocación inmediata (RF-051).

Hasta ahora solo existía `refresh:<token> → user_id`, sin forma de listar los tokens de
un usuario, y el access token (JWT, 30 min) no se podía invalidar. Desactivar a alguien
le dejaba hasta 30 minutos de acceso.

Claves en Redis:
  user_sessions:<user_id>   set con los refresh tokens vivos del usuario
  user_revoked_at:<user_id> instante (ms) de la última revocación; `get_current_auth`
                            rechaza los access tokens emitidos en ese instante o antes

Las API Keys no son sesiones de usuario y no pasan por aquí (RN-051-3).

Limitación conocida: los refresh tokens emitidos antes de desplegar esto no están en el
índice, así que un reseteo de contraseña no los cierra (hasta 7 días). Desactivar a un
usuario sí cierra todo: `refresh_session` rechaza a los usuarios inactivos.
"""
import time

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.security import refresh_key

SESSIONS_PREFIX = "user_sessions:"
REVOKED_PREFIX = "user_revoked_at:"


def sessions_key(user_id: str) -> str:
    return f"{SESSIONS_PREFIX}{user_id}"


def revoked_key(user_id: str) -> str:
    return f"{REVOKED_PREFIX}{user_id}"


async def register_session(user_id: str, refresh_token: str, redis: aioredis.Redis) -> None:
    """Anota el refresh token en el índice del usuario."""
    key = sessions_key(user_id)
    await redis.sadd(key, refresh_token)  # type: ignore[misc]
    await redis.expire(key, settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)


async def unregister_session(user_id: str, refresh_token: str, redis: aioredis.Redis) -> None:
    await redis.srem(sessions_key(user_id), refresh_token)  # type: ignore[misc]


async def revoke_all_sessions(user_id: str, redis: aioredis.Redis) -> int:
    """Cierra todas las sesiones del usuario. Devuelve cuántos refresh tokens invalidó."""
    key = sessions_key(user_id)
    tokens = await redis.smembers(key)  # type: ignore[misc]
    if tokens:
        await redis.delete(*[refresh_key(t) for t in tokens])
    await redis.delete(key)

    # El marcador solo hace falta mientras pueda vivir un access token anterior.
    ttl = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60
    await redis.set(revoked_key(user_id), int(time.time() * 1000), ex=ttl)
    return len(tokens)


async def is_revoked(user_id: str, payload: dict, redis: aioredis.Redis) -> bool:
    """¿El access token (ya decodificado) es anterior a la última revocación del usuario?"""
    revoked_at = await redis.get(revoked_key(user_id))
    if revoked_at is None:
        return False
    issued_ms = payload.get("iat_ms")
    if issued_ms is None:
        # Token emitido antes de que existiera `iat_ms`: se asume el último milisegundo de su segundo.
        issued_ms = int(payload.get("iat", 0)) * 1000 + 999
    return int(issued_ms) <= int(revoked_at)
