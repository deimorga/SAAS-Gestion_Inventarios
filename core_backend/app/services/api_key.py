from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key_pair
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from app.schemas.common import PaginatedResponse, PaginationMeta


async def list_api_keys(
    db: AsyncSession,
    tenant_id: str,
    page: int,
    page_size: int,
    is_active: bool | None,
) -> PaginatedResponse:
    query = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(ApiKey.is_active == is_active)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    rows = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    keys = rows.scalars().all()

    return PaginatedResponse(
        data=[ApiKeyResponse.model_validate(k) for k in keys],
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=-(-total // page_size),
        ),
    )


async def create_api_key(
    body: ApiKeyCreate,
    db: AsyncSession,
    tenant_id: str,
) -> ApiKeyCreateResponse:
    key_id, key_secret, key_hash = generate_api_key_pair()
    now = datetime.now(timezone.utc)

    api_key = ApiKey(
        id=str(uuid4()),
        tenant_id=tenant_id,
        key_id=key_id,
        key_hash=key_hash,
        name=body.name,
        scopes=[s.value for s in body.scopes],
        ip_whitelist=body.ip_whitelist,
        expires_at=body.expires_at,
        created_at=now,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreateResponse(
        **ApiKeyResponse.model_validate(api_key).model_dump(),
        key_secret=key_secret,
    )


async def revoke_api_key(key_id: str, db: AsyncSession, tenant_id: str) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key no encontrada")

    api_key.is_active = False
    await db.commit()
