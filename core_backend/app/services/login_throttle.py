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
import asyncio
import ipaddress
from collections.abc import Awaitable, Callable
from typing import TypeVar

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.core.config import settings

MAX_FAILURES_PER_ACCOUNT = 5
MAX_FAILURES_PER_IP = 20
LOCKOUT_SECONDS = 15 * 60

T = TypeVar("T")


async def _trusted_proxy_ips() -> set[str]:
    """IPs de TRUSTED_PROXY_HOSTS; los nombres se resuelven en cada llamada.

    Solo se usa en el login, así que el coste de resolver es despreciable, y
    resolver siempre evita confiar en una IP vieja tras recrear el contenedor.
    """
    loop = asyncio.get_running_loop()
    ips: set[str] = set()
    for host in filter(None, (h.strip() for h in settings.TRUSTED_PROXY_HOSTS.split(","))):
        try:
            ipaddress.ip_address(host)
            ips.add(host)
        except ValueError:
            try:
                infos = await loop.getaddrinfo(host, None)
            except OSError:
                continue  # contenedor caído o inexistente: no se confía en nada
            ips.update(str(info[4][0]) for info in infos)
    return ips


async def client_ip(request: Request) -> str:
    """IP real del cliente.

    X-Forwarded-For solo se cree si la conexión viene de un proxy de confianza:
    Traefik descarta el que envía el cliente y añade la IP de origen al final,
    y el portal reenvía igual la del navegador. inv-api está en la red
    compartida del gateway, así que cualquier otro contenedor podría llamarlo
    directo con la cabecera falseada; para esos cuenta la IP de la conexión.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and peer in await _trusted_proxy_ips():
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return peer


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
