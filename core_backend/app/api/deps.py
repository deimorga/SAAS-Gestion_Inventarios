"""Dependencias reutilizables de FastAPI.

Flujo de auth para endpoints protegidos:
  get_current_auth  →  valida JWT / API Key, aplica rate limit
  get_auth_db       →  abre sesión AsyncSession con RLS del tenant activo
  get_admin_db      →  abre sesión con bypass de RLS (solo super_admin)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, Literal

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.redis_client import get_redis
from app.core.security import (
    decode_access_token,
    hash_api_secret,
    rate_limit_key,
    rpm_for_tier,
)
from app.models.api_key import ApiKey

bearer_scheme = HTTPBearer(auto_error=False)

# UUID fijo del tenant interno — debe coincidir con la migración 012
MICRONUBA_TENANT_ID = "00000000-0000-0000-0000-000000000001"
# Sentinel que activa el bypass de RLS en las políticas de PostgreSQL
_SUPER_ADMIN_SENTINEL = "__super_admin__"


@dataclass
class AuthContext:
    user_id: str
    tenant_id: str
    role: str
    auth_type: Literal["jwt", "api_key"] = "jwt"
    scopes: list[str] = field(default_factory=list)
    tier: str = "STARTER"
    rate_limit_info: dict = field(default_factory=dict)
    # "full" para sesiones normales; "first_access" restringe a /auth/activate únicamente
    token_scope: str = "full"


# ── Rate limiting ──────────────────────────────────────────────────────────

async def _apply_rate_limit(tenant_id: str, tier: str, redis: aioredis.Redis) -> dict:
    key = rate_limit_key(tenant_id)
    limit = rpm_for_tier(tier)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)

    reset_ts = int(datetime.now(timezone.utc).timestamp() // 60 + 1) * 60

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes",
            headers={"Retry-After": "60"},
        )
    return {"limit": limit, "remaining": max(0, limit - count), "reset": reset_ts}


# ── Sesión pública (sin RLS) — solo para login ─────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ── Auth principal ─────────────────────────────────────────────────────────

async def get_current_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    token = credentials.credentials

    # ── Intentar JWT ───────────────────────────────────────────────────────
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise JWTError("tipo inválido")

        tenant_id = payload["tenant_id"]
        role = payload["role"]
        user_id = payload["sub"]
        token_scope = payload.get("scope", "full")

        tier_key = f"tenant_tier:{tenant_id}"
        tier = await redis.get(tier_key) or "STARTER"

        rl_info = await _apply_rate_limit(tenant_id, tier, redis)

        auth = AuthContext(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            auth_type="jwt",
            tier=tier,
            rate_limit_info=rl_info,
            token_scope=token_scope,
        )
        request.state.auth = auth
        return auth

    except JWTError:
        pass

    # ── Intentar API Key ───────────────────────────────────────────────────
    async with AsyncSessionLocal() as tmp_session:
        result = await tmp_session.execute(
            select(ApiKey).where(ApiKey.key_id == token[:60])
        )
        api_key = result.scalar_one_or_none()

    if api_key is None or not api_key.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key expirada")

    if hash_api_secret(token) != api_key.key_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    tier_key = f"tenant_tier:{api_key.tenant_id}"
    tier = await redis.get(tier_key) or "STARTER"
    rl_info = await _apply_rate_limit(api_key.tenant_id, tier, redis)

    auth = AuthContext(
        user_id=api_key.id,
        tenant_id=api_key.tenant_id,
        role="api_key",
        auth_type="api_key",
        scopes=api_key.scopes,
        tier=tier,
        rate_limit_info=rl_info,
    )
    request.state.auth = auth
    return auth


# ── Sesión con RLS activo ──────────────────────────────────────────────────

async def get_auth_db(
    auth: AuthContext = Depends(get_current_auth),
) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": auth.tenant_id},
        )
        yield session


# ── Guards de rol ──────────────────────────────────────────────────────────

def require_roles(*roles: str):
    async def _check(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if auth.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes")
        return auth
    return _check


require_admin = require_roles("tenant_admin", "super_admin")
require_catalog_read = require_roles("tenant_admin", "super_admin", "inventory_manager", "viewer")
require_catalog_write = require_roles("tenant_admin", "super_admin", "inventory_manager")
require_inventory_read = require_roles("tenant_admin", "super_admin", "inventory_manager", "viewer")
require_inventory_write = require_roles("tenant_admin", "super_admin", "inventory_manager")


# ── Guard exclusivo super_admin ────────────────────────────────────────────

async def require_super_admin(
    auth: AuthContext = Depends(get_current_auth),
) -> AuthContext:
    # 403 genérico — no revela que el endpoint de admin existe para otros roles
    if auth.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")
    return auth


# ── Sesión con bypass de RLS — exclusiva para super_admin ─────────────────

async def get_admin_db(
    _auth: AuthContext = Depends(require_super_admin),
) -> AsyncGenerator[AsyncSession, None]:
    """Abre una sesión PostgreSQL con el sentinel __super_admin__ en
    app.current_tenant, lo que activa el bypass de RLS definido en
    la migración 012 para users, api_keys y audit_logs."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :sentinel, true)"),
            {"sentinel": _SUPER_ADMIN_SENTINEL},
        )
        yield session
