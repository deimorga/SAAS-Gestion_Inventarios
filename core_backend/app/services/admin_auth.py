from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    refresh_key,
    verify_password,
)
from app.models.user import User
from app.schemas.admin_auth import AdminLoginResponse, AdminRegisterRequest
from app.schemas.auth import UserRole, UserSummary

MICRONUBA_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def register_super_admin(
    request: AdminRegisterRequest,
    bootstrap_secret: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> AdminLoginResponse:
    if not settings.ADMIN_BOOTSTRAP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bootstrap de admin deshabilitado",
        )
    if bootstrap_secret != settings.ADMIN_BOOTSTRAP_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    result = await db.execute(select(User).where(User.role == "super_admin"))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un super_admin registrado",
        )

    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado")

    user = User(
        tenant_id=MICRONUBA_TENANT_ID,
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role="super_admin",
        is_active=True,
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return await _issue_admin_tokens(user, redis)


async def login_super_admin(
    email: str,
    password: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> AdminLoginResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    # Separación de superficies: solo super_admin puede usar esta ruta
    if user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta suspendida. Contacte soporte.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return await _issue_admin_tokens(user, redis)


async def _issue_admin_tokens(user: User, redis: aioredis.Redis) -> AdminLoginResponse:
    access_token, expires_in = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
    )
    refresh_token = generate_refresh_token()
    ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(refresh_key(refresh_token), ttl, user.id)

    return AdminLoginResponse(
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
