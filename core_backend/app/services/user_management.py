import secrets
from datetime import datetime, timezone
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user_management import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services.activation import generate_activation_token

# Roles que un tenant_admin puede crear (D-04: no puede escalar privilegios)
_ALLOWED_ROLES = {"api_consumer", "inventory_manager", "viewer"}


async def create_user(
    request: UserCreate,
    tenant_id: str,
    created_by_user_id: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> UserResponse:
    if request.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Un tenant_admin no puede crear usuarios con rol '{request.role}'",
        )

    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado en este tenant",
        )

    user_id = str(uuid4())
    now = datetime.now(timezone.utc)
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=request.email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=request.full_name,
        role=request.role,
        is_active=False,
        must_change_password=True,
        created_by=created_by_user_id,
        created_at=now,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Token de activación (F-4 /auth/activate lo consume)
    await generate_activation_token(user.id, redis)

    return UserResponse.model_validate(user)


async def list_users(
    tenant_id: str,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> UserListResponse:
    offset = (page - 1) * size
    total = (
        await db.execute(select(func.count()).select_from(User).where(User.tenant_id == tenant_id))
    ).scalar_one()
    users = (
        await db.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(size)
        )
    ).scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
    )


async def update_user(
    user_id: str,
    tenant_id: str,
    request: UserUpdate,
    db: AsyncSession,
) -> UserResponse:
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    updates = request.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
