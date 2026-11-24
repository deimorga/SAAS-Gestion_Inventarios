import re
import secrets
from datetime import datetime, timezone
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.services.activation import dispatch_activation_email, generate_activation_token
from app.services.warehouse import DEFAULT_WAREHOUSE_CODE, provision_default_warehouse
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.admin_tenant import (
    TenantCreate,
    TenantCreateResponse,
    TenantListResponse,
    TenantResponse,
    TenantUpdate,
)


# R-08: si dos altas llegan a la vez, las comprobaciones previas no ven a la otra y es el índice
# único el que decide. Se responde 409 con el mismo motivo que daría la comprobación previa.
_CONFLICTOS_ALTA = {
    "uq_tenants_external_ref": "Ya existe un tenant con ese external_provider/external_id",
    "idx_tenants_slug": "El slug ya está en uso",
    "uq_users_email_lower": "El email de administrador ya está registrado",
    "idx_users_email_tenant": "El email de administrador ya está registrado",
}


def _detalle_conflicto(exc: IntegrityError, *, auto_slug: bool = False) -> str:
    mensaje = str(exc.orig)
    if auto_slug and "idx_tenants_slug" in mensaje:
        # El slug lo calculó el sistema, no el cliente: no es «tu slug está en uso» sino una carrera
        return "Otra alta con el mismo nombre se estaba registrando al mismo tiempo; reintenta"
    for constraint, detalle in _CONFLICTOS_ALTA.items():
        if constraint in mensaje:
            return detalle
    return "El tenant choca con otro registrado al mismo tiempo; reintenta"


async def _ensure_external_ref_free(db: AsyncSession, provider: str, external_id: str) -> None:
    """409 si ya hay un tenant con ese id externo. El `detail` lleva su `tenant_id`: la
    plataforma lo usa para recuperar la sede tras un reintento (doc/integracion/plataforma_sedes.md)."""
    result = await db.execute(
        select(Tenant).where(Tenant.external_provider == provider, Tenant.external_id == external_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un tenant para {provider}:{external_id} (tenant_id={existing.id})",
        )


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or "tenant"


async def create_tenant(
    request: TenantCreate,
    created_by_user_id: str,
    db: AsyncSession,
    redis: aioredis.Redis,
    *,
    warehouse_code: str = DEFAULT_WAREHOUSE_CODE,
    warehouse_name: str = "Bodega Principal",
    warehouse_address: str | None = None,
    notify_admin: bool = True,
) -> TenantCreateResponse:
    """`notify_admin=False`: no genera el enlace de activación ni manda el email; lo hace quien
    llama cuando el alta está completa (el aprovisionamiento por plataforma, R-07)."""
    slug = request.slug if request.slug else _slugify(request.name)

    if request.external_id and not request.external_provider:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="external_id requiere external_provider",
        )
    if request.external_provider and request.external_id:
        await _ensure_external_ref_free(db, request.external_provider, request.external_id)
    parent: Tenant | None = None
    if request.parent_tenant_id:
        parent = (
            await db.execute(select(Tenant).where(Tenant.id == str(request.parent_tenant_id)))
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="parent_tenant_id no corresponde a ningún tenant",
            )
        # Un solo nivel: las sedes cuelgan de un principal, nunca de otra sede.
        if parent.parent_tenant_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Una sede no puede tener sedes; crea la sede desde el tenant principal",
            )

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if result.scalar_one_or_none() is not None:
        if request.slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El slug ya está en uso",
            )
        slug = f"{slug}-{uuid4().hex[:8]}"

    admin_email = request.admin_email.strip().lower()
    result = await db.execute(select(User.id).where(func.lower(User.email) == admin_email).limit(1))
    if result.first() is not None:
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
        # El plan lo define el tenant principal: una sede nace con el suyo y lo sigue. Sin principal
        # no hay de quién heredar y se respeta el que se pida.
        subscription_tier=parent.subscription_tier if parent else request.subscription_tier,
        config={},
        is_active=True,
        tax_id=request.tax_id,
        external_provider=request.external_provider,
        external_id=request.external_id,
        parent_tenant_id=str(request.parent_tenant_id) if request.parent_tenant_id else None,
        created_at=now,
        updated_at=now,
    )
    db.add(tenant)

    admin_user = User(
        tenant_id=tenant_id,
        email=admin_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        full_name=request.admin_full_name,
        role="tenant_admin",
        is_active=False,
        must_change_password=True,
        created_by=created_by_user_id,
        created_at=now,
    )
    db.add(admin_user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # Un reintento idéntico (mismo nombre → mismo slug, mismo external_id) puede chocar primero por
        # el slug: PostgreSQL reporta el primer índice único que revisa. Sea cual sea el que saltó, si
        # el id externo ya existe el 409 es el de siempre, con el tenant_id del que ganó la carrera.
        if request.external_provider and request.external_id:
            await _ensure_external_ref_free(db, request.external_provider, request.external_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_detalle_conflicto(exc, auto_slug=not request.slug)
        ) from exc
    await db.refresh(tenant)
    await db.refresh(admin_user)

    # Almacén inicial: sin él el tenant puede crear productos pero no darles stock.
    warehouse = await provision_default_warehouse(
        tenant_id, code=warehouse_code, name=warehouse_name, location_address=warehouse_address
    )

    if notify_admin:
        await notify_tenant_admin(admin_user.id, admin_user.email, admin_user.full_name, redis)

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
        warehouse_id=warehouse.id if warehouse else None,
    )


async def notify_tenant_admin(user_id: str, email: str, full_name: str, redis: aioredis.Redis) -> None:
    """Enlace de activación del admin de un tenant nuevo (consumido por /auth/activate).

    El tenant ya está creado: si el email no se puede encolar se registra y se sigue. El
    administrador puede reenviarlo desde el portal.
    """
    activation_token = await generate_activation_token(user_id, redis)
    dispatch_activation_email(to_email=email, full_name=full_name, token=activation_token, template="tenant_created")


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
    if "subscription_tier" in updates and tenant.parent_tenant_id is not None:
        # `tenants` no está bajo RLS. Si la principal ya no existe, la sede queda libre de cambiar el suyo.
        if await db.get(Tenant, str(tenant.parent_tenant_id)) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El plan de una sede lo define su tenant principal: cámbialo en el principal",
            )
    for field, value in updates.items():
        setattr(tenant, field if field != "subscription_tier" else "subscription_tier", value)

    if "subscription_tier" in updates:
        # Las sedes siguen el plan de su principal: se actualizan en la misma transacción
        await db.execute(
            update(Tenant).where(Tenant.parent_tenant_id == tenant.id).values(subscription_tier=updates["subscription_tier"])
        )

    tenant.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tenant)
    return TenantResponse.model_validate(tenant)
