from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    refresh_key,
    verify_password,
)
from app.core.config import settings
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import TokenResponse, RefreshResponse, UserSummary, UserRole
from app.services.sessions import register_session, unregister_session


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    # El email es único sin distinguir mayúsculas (RN-052-1/2)
    result = await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta suspendida. Contacte soporte.")

    # Separación de superficies: super_admin debe usar /admin/auth/login
    if user.role == "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result_tenant = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result_tenant.scalar_one_or_none()

    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta suspendida. Contacte soporte.")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    return user


async def issue_tokens(user: User, redis: aioredis.Redis) -> TokenResponse:
    access_token, expires_in = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role
    )
    refresh_token = generate_refresh_token()
    ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(refresh_key(refresh_token), ttl, user.id)
    await register_session(user.id, refresh_token, redis)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=UserRole(user.role),
            tenant_id=user.tenant_id,
        ),
    )


async def refresh_session(refresh_token: str, db: AsyncSession, redis: aioredis.Redis) -> RefreshResponse:
    user_id = await redis.get(refresh_key(refresh_token))
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido o expirado")

    await redis.delete(refresh_key(refresh_token))
    await unregister_session(user_id, refresh_token, redis)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta suspendida. Contacte soporte.")

    result_tenant = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result_tenant.scalar_one_or_none()
    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta suspendida. Contacte soporte.")

    access_token, expires_in = create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role
    )
    new_refresh = generate_refresh_token()
    ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(refresh_key(new_refresh), ttl, user.id)
    await register_session(user.id, new_refresh, redis)

    return RefreshResponse(access_token=access_token, refresh_token=new_refresh, expires_in=expires_in)


async def logout(refresh_token: str, redis: aioredis.Redis) -> None:
    user_id = await redis.get(refresh_key(refresh_token))
    await redis.delete(refresh_key(refresh_token))
    if user_id:
        await unregister_session(user_id, refresh_token, redis)
