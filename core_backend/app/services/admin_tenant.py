import re
import secrets
from datetime import datetime, timezone
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.admin_tenant import (
    TenantCreate,
    TenantCreateResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or "tenant"


async def create_tenant(
    request: TenantCreate,
    created_by_user_id: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> TenantCreateResponse:
    slug = request.slug if request.slug else _slugify(request.name)

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if result.scalar_one_or_none() is not None:
        if request.slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El slug ya está en uso",
            )
        slug = f"{slug}-{uuid4().hex[:8]}"

    result = await db.execute(select(User).where(User.email == request.admin_email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email de administrador ya está registrado",
        )

    now = datetime.now(timezone.utc)
    # El default=lambda de SQLAlchemy 2.0 se aplica en INSERT, no en __init__.
    # Pre-generamos el UUID para poder usarlo en el User antes del flush.
    tenant_id = str(uuid4())
    tenant = Tenant(
        id=tenant_id,
        name=request.name,
        slug=slug,
        subscription_tier=request.subscription_tier,
        config={},
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(tenant)

    admin_user = User(
        tenant_id=tenant_id,
        email=request.admin_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=request.admin_full_name,
        role="tenant_admin",
        is_active=False,
        must_change_password=True,
        created_by=created_by_user_id,
        created_at=now,
    )
    db.add(admin_user)
    await db.commit()
    await db.refresh(tenant)
    await db.refresh(admin_user)

    # Token de activación almacenado en Redis (consumido por F-4 /auth/activate)
    activation_token = secrets.token_urlsafe(32)
    ttl_seconds = settings.ACTIVATION_TOKEN_TTL_HOURS * 3600
    await redis.setex(f"activation:{activation_token}", ttl_seconds, admin_user.id)

    return TenantCreateResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        subscription_tier=tenant.subscription_tier,
        is_active=tenant.is_active,
        config=tenant.config,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        admin_user_id=admin_user.id,
        admin_email=admin_user.email,
    )


async def list_tenants(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> TenantListResponse:
    offset = (page - 1) * size

    total = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()
    tenants = (
        await db.execute(
            select(Tenant).order_by(Tenant.created_at.desc()).offset(offset).limit(size)
        )
    ).scalars().all()

    return TenantListResponse(
        items=[TenantResponse.model_validate(t) for t in tenants],
        total=total,
        page=page,
        size=size,
    )


async def get_tenant(tenant_id: str, db: AsyncSession) -> TenantResponse:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")
    return TenantResponse.model_validate(tenant)


async def update_tenant(
    tenant_id: str,
    request: TenantUpdate,
    db: AsyncSession,
) -> TenantResponse:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")

    updates = request.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(tenant, field if field != "subscription_tier" else "subscription_tier", value)

    tenant.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)
