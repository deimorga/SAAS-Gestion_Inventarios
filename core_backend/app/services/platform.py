"""Aprovisionamiento de tenants por una plataforma externa (Appits).

Una sede creada en Appits nace aquí como tenant propio — catálogo y stock
aislados del taller principal por RLS — con su almacén físico y su API key,
en una sola llamada.

Sesiones: `tenants` no está bajo RLS, pero `users` y `api_keys` sí (FORCE).
El alta del tenant y su admin usa el contexto de sistema, igual que el panel
de administración; todo lo que toca datos del tenant nuevo (API key, almacén,
auditoría) va con el contexto RLS de ese tenant.
"""

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, set_system_context, set_tenant_context
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.schemas.admin_tenant import TenantCreate
from app.schemas.api_key import ApiKeyCreate
from app.schemas.platform import (
    PlatformApiKey,
    PlatformTenantCreate,
    PlatformTenantCreated,
    PlatformTenantDeactivated,
    PlatformTenantInfo,
    PlatformWarehouse,
    PlatformZone,
)
from app.services import warehouse as wh_service
from app.services.admin_tenant import create_tenant
from app.services.api_key import create_api_key
from app.services.audit import log_action


def platform_key_performer(platform_key_id: str) -> dict:
    return {"type": "api_key", "id": platform_key_id}


def admin_user_performer(user_id: str) -> dict:
    return {"type": "user", "id": user_id}


async def _warehouse_with_zones(session: AsyncSession, tenant_id: str, wh) -> PlatformWarehouse:
    zones = await wh_service.list_zones(warehouse_id=str(wh.id), db=session, tenant_id=tenant_id)
    return PlatformWarehouse(
        id=wh.id,
        code=wh.code,
        name=wh.name,
        zones=[PlatformZone(id=z.id, code=z.code, zone_type=z.zone_type) for z in zones],
    )


async def _get_platform_tenant(session: AsyncSession, tenant_id: str) -> Tenant:
    """Solo tenants aprovisionados por una plataforma. Los creados a mano en el
    panel no existen para `/v1/platform/*`: 404, no 403, para no revelarlos."""
    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.external_provider.is_not(None))
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")
    return tenant


async def provision_tenant(
    body: PlatformTenantCreate,
    performed_by: dict,
    redis: aioredis.Redis,
) -> PlatformTenantCreated:
    """`performed_by`: quién lo pide, para auditoría y `users.created_by` —
    la API key de plataforma (Appits) o el super_admin desde el panel."""
    tenant_request = TenantCreate(
        name=body.name,
        subscription_tier=body.subscription_tier,
        admin_email=body.admin_email,
        admin_full_name=body.admin_full_name,
        tax_id=body.tax_id,
        external_provider=body.external_provider,
        external_id=body.external_id,
        parent_tenant_id=body.parent_tenant_id,
    )

    async with AsyncSessionLocal() as session:
        await set_system_context(session)
        created = await create_tenant(
            tenant_request,
            created_by_user_id=performed_by["id"],
            db=session,
            redis=redis,
            warehouse_code=body.warehouse.code,
            warehouse_name=body.warehouse.name,
            warehouse_address=body.warehouse.location_address,
        )

    tenant_id = str(created.id)

    # Sin almacén la sede no puede recibir stock: no vale devolver un tenant a medias.
    if created.warehouse_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant {tenant_id} creado pero sin almacén inicial; revisar logs",
        )

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)

        key = await create_api_key(
            ApiKeyCreate(name=body.api_key_name, scopes=body.api_key_scopes),
            db=session,
            tenant_id=tenant_id,
        )
        wh = await wh_service.get_warehouse(str(created.warehouse_id), db=session, tenant_id=tenant_id)
        warehouse = await _warehouse_with_zones(session, tenant_id, wh)

        await log_action(
            db=session,
            tenant_id=tenant_id,
            entity="tenants",
            entity_id=tenant_id,
            action="CREATE",
            new_values={
                "via": "platform",
                "external_provider": body.external_provider,
                "external_id": body.external_id,
                "parent_tenant_id": str(body.parent_tenant_id) if body.parent_tenant_id else None,
                "warehouse_id": str(wh.id),
                "api_key_id": str(key.id),
            },
            performed_by=performed_by,
        )

    return PlatformTenantCreated(
        tenant_id=created.id,
        slug=created.slug,
        name=created.name,
        external_provider=body.external_provider,
        external_id=body.external_id,
        parent_tenant_id=body.parent_tenant_id,
        admin_user_id=created.admin_user_id,
        admin_email=created.admin_email,
        warehouse=warehouse,
        api_key=PlatformApiKey(
            id=key.id,
            key_id=key.key_id,
            key_secret=key.key_secret,
            scopes=[s.value for s in key.scopes],
            expires_at=key.expires_at,
        ),
    )


async def _tenant_info(tenant: Tenant) -> PlatformTenantInfo:
    tenant_id = str(tenant.id)
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        warehouses = await wh_service.list_warehouses(db=session, tenant_id=tenant_id)
        detailed = [await _warehouse_with_zones(session, tenant_id, w) for w in warehouses]
    return PlatformTenantInfo(
        tenant_id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        is_active=tenant.is_active,
        tax_id=tenant.tax_id,
        external_provider=tenant.external_provider,
        external_id=tenant.external_id,
        parent_tenant_id=tenant.parent_tenant_id,
        warehouses=detailed,
        created_at=tenant.created_at,
    )


async def get_tenant_info(tenant_id: str) -> PlatformTenantInfo:
    async with AsyncSessionLocal() as session:
        tenant = await _get_platform_tenant(session, tenant_id)
    return await _tenant_info(tenant)


async def get_tenant_by_external(provider: str, external_id: str) -> PlatformTenantInfo:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(
                Tenant.external_provider == provider, Tenant.external_id == external_id
            )
        )
        tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")
    return await _tenant_info(tenant)


async def deactivate_tenant(tenant_id: str, performed_by: dict) -> PlatformTenantDeactivated:
    """Baja lógica: el tenant queda suspendido y sus API keys revocadas.

    Nunca se borra el inventario: si la sede se elimina por error en Appits, los
    datos siguen ahí y el tenant se reactiva desde el panel de administración.
    """
    async with AsyncSessionLocal() as session:
        tenant = await _get_platform_tenant(session, tenant_id)
        tenant.is_active = False
        await session.commit()

    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            update(ApiKey)
            .where(ApiKey.tenant_id == tenant_id, ApiKey.is_active.is_(True))
            .values(is_active=False)
        )
        revoked = result.rowcount or 0
        await log_action(
            db=session,
            tenant_id=tenant_id,
            entity="tenants",
            entity_id=tenant_id,
            action="UPDATE",
            old_values={"is_active": True},
            new_values={"via": "platform", "is_active": False, "api_keys_revoked": revoked},
            performed_by=performed_by,
        )
        await session.commit()

    return PlatformTenantDeactivated(tenant_id=tenant_id, is_active=False, api_keys_revoked=revoked)


async def list_children(parent_tenant_id: str) -> list[Tenant]:
    """Sedes (tenants hijos) de un tenant, más recientes primero."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant)
            .where(Tenant.parent_tenant_id == parent_tenant_id)
            .order_by(Tenant.created_at.desc())
        )
        return list(result.scalars().all())
