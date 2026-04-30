from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import generate_api_key_pair
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.schemas.api_key import ApiKeyCreateResponse, ApiKeyResponse
from app.schemas.common import PaginatedResponse, PaginationMeta


async def _staggered_expiry() -> datetime:
    """Calcula la fecha de expiración para una nueva key evitando colisiones entre tenants.

    Parte de now + API_KEY_EXPIRY_DAYS y avanza de a 1 día hasta encontrar una fecha
    libre (sin otra key activa que expire ese día). Máximo desplazamiento: 14 días.
    """
    base = datetime.now(timezone.utc) + timedelta(days=settings.API_KEY_EXPIRY_DAYS)

    async with AsyncSessionLocal() as session:
        for offset in range(15):
            candidate = base + timedelta(days=offset)
            candidate_date = candidate.date()
            taken = (
                await session.execute(
                    select(ApiKey).where(
                        ApiKey.is_active,
                        func.date(ApiKey.expires_at) == candidate_date,
                    )
                )
            ).scalar_one_or_none()
            if taken is None:
                return candidate

    return base + timedelta(days=14)


async def rotate_api_key(
    key_uuid: str,
    tenant_id: str,
    immediate: bool,
    db: AsyncSession,
) -> ApiKeyCreateResponse:
    """Crea una nueva API Key con los mismos atributos que la existente.

    Si `immediate=True`, revoca la clave anterior al instante.
    Si `immediate=False`, la deja activa durante el período de gracia configurado
    (la tarea Celery revoke_grace_period_key la revocará automáticamente — F-7).
    """
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_uuid, ApiKey.tenant_id == tenant_id)
    )
    old_key = result.scalar_one_or_none()
    if old_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key no encontrada")
    if not old_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede rotar una API Key inactiva",
        )

    expires_at = await _staggered_expiry()
    new_key_id, new_secret, new_hash = generate_api_key_pair()
    now = datetime.now(timezone.utc)

    new_key = ApiKey(
        id=str(__import__("uuid").uuid4()),
        tenant_id=tenant_id,
        key_id=new_key_id,
        key_hash=new_hash,
        name=old_key.name,
        scopes=old_key.scopes,
        ip_whitelist=old_key.ip_whitelist,
        expires_at=expires_at,
        is_active=True,
        created_at=now,
    )
    db.add(new_key)

    if immediate:
        old_key.is_active = False

    await db.commit()
    await db.refresh(new_key)

    return ApiKeyCreateResponse(
        **ApiKeyResponse.model_validate(new_key).model_dump(),
        key_secret=new_secret,
    )


# ── Admin: gestión cross-tenant de API Keys ────────────────────────────────


async def admin_list_tenant_api_keys(
    tenant_id: str,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    is_active: bool | None = None,
) -> PaginatedResponse:
    query = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(ApiKey.is_active == is_active)

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    keys = (
        await db.execute(query.offset((page - 1) * size).limit(size))
    ).scalars().all()

    return PaginatedResponse(
        data=[ApiKeyResponse.model_validate(k) for k in keys],
        pagination=PaginationMeta(
            page=page,
            page_size=size,
            total_items=total,
            total_pages=-(-total // size),
        ),
    )


async def admin_revoke_api_key(
    tenant_id: str,
    key_uuid: str,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_uuid, ApiKey.tenant_id == tenant_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key no encontrada")

    # Verificar que el tenant existe (previene confusión si el UUID de tenant no existe)
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")

    key.is_active = False
    await db.commit()
