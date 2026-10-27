"""Límite de intentos fallidos de login.

El rate limit general se aplica después de autenticar, así que los endpoints de
login no tenían ningún freno: se podían probar contraseñas sin límite, también
contra el super_admin expuesto en internet.

Dos contadores en Redis, ambos de ventana fija desde el primer fallo:
  - cuenta + IP : frena la fuerza bruta contra un usuario desde un origen. Ir por
                  cuenta + IP y no solo por cuenta evita que un atacante bloquee
                  al dueño legítimo, que entra desde otra IP.
  - IP          : frena el credential stuffing (muchos emails, un origen).
Solo cuenta una contraseña rechazada (401). Un 403 implica que era correcta.
"""
from collections.abc import Awaitable, Callable
from typing import TypeVar

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

MAX_FAILURES_PER_ACCOUNT = 5
MAX_FAILURES_PER_IP = 20
LOCKOUT_SECONDS = 15 * 60

T = TypeVar("T")


def client_ip(request: Request) -> str:
    """IP real del cliente.

    Detrás de Traefik la conexión llega desde el proxy; Traefik descarta el
    X-Forwarded-For que envía el cliente y añade la IP de origen al final, así
    que el último elemento es el fiable. El portal, que llama por la red interna,
    reenvía del mismo modo la IP del navegador.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


def _account_key(email: str, ip: str) -> str:
    return f"login_fail:acct:{email.strip().lower()}:{ip}"


def _ip_key(ip: str) -> str:
    return f"login_fail:ip:{ip}"


async def _ensure_not_blocked(redis: aioredis.Redis, email: str, ip: str) -> None:
    for key, limit in ((_account_key(email, ip), MAX_FAILURES_PER_ACCOUNT), (_ip_key(ip), MAX_FAILURES_PER_IP)):
        failures = int(await redis.get(key) or 0)
        if failures >= limit:
            ttl = await redis.ttl(key)
            retry_after = ttl if ttl > 0 else LOCKOUT_SECONDS
            minutes = max(1, -(-retry_after // 60))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutes} min.",
                headers={"Retry-After": str(retry_after)},
            )


async def _record_failure(redis: aioredis.Redis, email: str, ip: str) -> None:
    for key in (_account_key(email, ip), _ip_key(ip)):
        if await redis.incr(key) == 1:
            await redis.expire(key, LOCKOUT_SECONDS)


async def throttled_login(
    redis: aioredis.Redis,
    email: str,
    ip: str,
    attempt: Callable[[], Awaitable[T]],
) -> T:
    """Ejecuta `attempt` solo si el origen no está bloqueado y contabiliza el resultado."""
    await _ensure_not_blocked(redis, email, ip)
    try:
        result = await attempt()
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            await _record_failure(redis, email, ip)
        raise
    await redis.delete(_account_key(email, ip))
    return result
