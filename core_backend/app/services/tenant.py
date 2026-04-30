from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.schemas.tenant import TenantConfigResponse, TenantConfigUpdate

_DEFAULT_CONFIG = {
    "allow_negative_stock": False,
    "valuation_method": "CPP",
    "auto_reserve_on_order": False,
    "reservation_ttl_minutes": 30,
    "low_stock_alert_enabled": True,
    "require_reason_code": True,
    "default_currency": "COP",
    "timezone": "America/Bogota",
    # API Key rotation: días de gracia antes de revocar la key anterior tras una rotación.
    # Rango permitido: 7–90. El sistema no permite solapar fechas de expiración entre tenants.
    "api_key_rotation_grace_days": 30,
}


async def get_tenant_config(tenant_id: str, db: AsyncSession) -> TenantConfigResponse:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")

    return TenantConfigResponse(
        tenant_id=tenant.id,
        config={**_DEFAULT_CONFIG, **tenant.config},
        subscription_tier=tenant.subscription_tier,
        updated_at=tenant.updated_at,
    )


async def update_tenant_config(
    tenant_id: str,
    body: TenantConfigUpdate,
    db: AsyncSession,
) -> TenantConfigResponse:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")

    updates = body.model_dump(exclude_none=True)

    # RN-005-2: no se puede cambiar el método de valoración con movimientos activos
    # (inventory_ledger se implementa en Sprint 2 — validación pendiente)
    if "valuation_method" in updates and updates["valuation_method"] != tenant.config.get("valuation_method"):
        pass  # TODO Sprint 2: verificar inventory_ledger del período actual

    merged = {**tenant.config, **updates}
    tenant.config = merged
    tenant.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tenant)

    return TenantConfigResponse(
        tenant_id=tenant.id,
        config={**_DEFAULT_CONFIG, **tenant.config},
        subscription_tier=tenant.subscription_tier,
        updated_at=tenant.updated_at,
    )
