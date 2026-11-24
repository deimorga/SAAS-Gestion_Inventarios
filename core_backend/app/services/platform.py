"""Aprovisionamiento de tenants por una plataforma externa (Appits).

Una sede creada en Appits nace aquí como tenant propio — catálogo y stock
aislados del taller principal por RLS — con su almacén físico y su API key,
en una sola llamada.

Sesiones: `tenants` no está bajo RLS, pero `users` y `api_keys` sí (FORCE).
El alta del tenant y su admin usa el contexto de sistema, igual que el panel
de administración; todo lo que toca datos del tenant nuevo (API key, almacén,
auditoría) va con el contexto RLS de ese tenant.
"""

import logging

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, set_system_context, set_tenant_context
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.schemas.admin_tenant import TenantCreate, TenantCreateResponse
from app.schemas.api_key import ApiKeyCreate
from app.schemas.platform import (
    PANEL_PROVIDER,
    PlatformApiKey,
    PlatformTenantCreate,
    PlatformTenantCreated,
    PlatformTenantDeactivated,
    PlatformTenantInfo,
    PlatformWarehouse,
    PlatformZone,
)
from app.services import warehouse as wh_service
from app.services.admin_tenant import create_tenant, notify_tenant_admin
from app.services.api_key import create_api_key
from app.services.audit import log_action

logger = logging.getLogger(__name__)


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
    panel no existen para `/v1/platform/*`: 404, no 403, para no revelarlos.

    R-06: las sedes creadas desde el panel también llevan proveedor (`panel`), así que no basta
    con `external_provider IS NOT NULL`.
    """
    result = await session.execute(
        select(Tenant).where(
            Tenant.id == tenant_id,
            Tenant.external_provider.is_not(None),
            Tenant.external_provider != PANEL_PROVIDER,
        )
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
            notify_admin=False,  # el enlace se manda cuando la sede está completa
        )

    tenant_id = str(created.id)

    # R-07: todo o nada. Si falla un paso posterior al alta del tenant, se borra lo creado en esta
    # llamada para que el reintento con el mismo external_id funcione en vez de dar 409 sin key.
    try:
        result = await _complete_provisioning(body, created, performed_by)
    except HTTPException:
        await _undo_provisioning(tenant_id)  # un rechazo con su propio código: se deshace igual
        raise
    except Exception as exc:
        logger.exception("Aprovisionamiento de %s:%s fallido; se deshace", body.external_provider, body.external_id)
        if not await _undo_provisioning(tenant_id):
            # No se puede prometer «no se creó nada»: el reintento daría 409 sobre una sede sin key
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "No se pudo aprovisionar la sede y tampoco deshacer lo creado "
                    f"(tenant_id={tenant_id}); avisar a soporte de MicroNuba"
                ),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo aprovisionar la sede y no se creó nada; se puede reintentar",
        ) from exc

    # La sede ya está completa y la key solo se devuelve ahora: un fallo del aviso (Redis, Celery) se
    # registra pero no la tumba. El admin puede pedir el reenvío de la activación desde el panel.
    try:
        await notify_tenant_admin(str(created.admin_user_id), created.admin_email, body.admin_full_name, redis)
    except Exception:
        logger.exception("No se pudo enviar el enlace de activación del admin del tenant %s", tenant_id)
    return result


async def _undo_provisioning(tenant_id: str) -> bool:
    """Borra un tenant recién creado y todo lo suyo (las FK hacia `tenants` son ON DELETE CASCADE).

    Solo se llama con el id que acaba de crear esta misma llamada, antes de devolverlo a nadie.
    Devuelve si pudo: si no, quien llama no debe decirle al cliente que no se creó nada.
    """
    try:
        async with AsyncSessionLocal() as session:
            await set_system_context(session)
            await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await session.commit()
        return True
    except Exception:
        logger.exception("No se pudo deshacer el tenant %s a medias; revisarlo a mano", tenant_id)
        return False


async def _complete_provisioning(
    body: PlatformTenantCreate, created: TenantCreateResponse, performed_by: dict
) -> PlatformTenantCreated:
    """Almacén, API key y auditoría de una sede cuyo tenant y admin ya están creados."""
    tenant_id = str(created.id)

    # Sin almacén la sede no puede recibir stock: no vale devolver un tenant a medias.
    if created.warehouse_id is None:
        raise RuntimeError(f"Tenant {tenant_id} sin almacén inicial")

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
    if provider == PANEL_PROVIDER:  # R-06: las sedes del panel no existen para la plataforma
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant no encontrado")
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
