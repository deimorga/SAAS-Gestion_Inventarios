from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_balance import StockBalance
from app.models.warehouse import Warehouse
from app.models.zone import Zone
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate, ZoneCreate, ZoneUpdate


# ── Warehouse CRUD ────────────────────────────────────────────────────────────

async def create_warehouse(body: WarehouseCreate, db: AsyncSession, tenant_id: str) -> Warehouse:
    existing = await db.execute(
        select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un almacén con el código '{body.code}'")

    now = datetime.now(timezone.utc)
    wh = Warehouse(
        tenant_id=tenant_id,
        code=body.code,
        name=body.name,
        location_address=body.location_address,
        is_virtual=body.is_virtual,
        is_active=True,
        timezone=body.timezone or "UTC",
        created_at=now,
        updated_at=now,
    )
    db.add(wh)
    await db.flush()

    # Auto-create operational zones for physical warehouses (RF-015 logic)
    if not body.is_virtual:
        for zone_type in ("RECEIVING", "DISPATCH", "QUARANTINE"):
            code = f"{body.code}-{zone_type}"
            zone = Zone(
                tenant_id=tenant_id,
                warehouse_id=wh.id,
                code=code,
                name=f"{zone_type.capitalize()} — {body.name}",
                zone_type=zone_type,
                path=code,
                is_active=True,
                created_at=now,
            )
            db.add(zone)

    await db.commit()
    await db.refresh(wh)
    return wh


async def list_warehouses(
    db: AsyncSession,
    tenant_id: str,
    is_active: bool = True,
    is_virtual: bool | None = None,
) -> list[Warehouse]:
    q = select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.is_active == is_active)
    if is_virtual is not None:
        q = q.where(Warehouse.is_virtual == is_virtual)
    result = await db.execute(q.order_by(Warehouse.code))
    return list(result.scalars().all())


async def get_warehouse(warehouse_id: str, db: AsyncSession, tenant_id: str) -> Warehouse:
    result = await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Almacén no encontrado")
    return wh


async def update_warehouse(warehouse_id: str, body: WarehouseUpdate, db: AsyncSession, tenant_id: str) -> Warehouse:
    wh = await get_warehouse(warehouse_id, db, tenant_id)

    # RN-013-2: Cannot deactivate a warehouse that has stock
    if body.is_active is False and wh.is_active:
        total_result = await db.execute(
            select(func.sum(StockBalance.physical_qty)).where(
                StockBalance.warehouse_id == warehouse_id,
                StockBalance.tenant_id == tenant_id,
            )
        )
        total_stock = total_result.scalar_one_or_none() or 0
        if total_stock > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede desactivar un almacén con inventario físico > 0",
            )

    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(wh, k, v)
    wh.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(wh)
    return wh


# ── Zone CRUD ─────────────────────────────────────────────────────────────────

async def create_zone(warehouse_id: str, body: ZoneCreate, db: AsyncSession, tenant_id: str) -> Zone:
    wh = await get_warehouse(warehouse_id, db, tenant_id)
    if not wh.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El almacén está inactivo")

    existing = await db.execute(
        select(Zone).where(Zone.warehouse_id == warehouse_id, Zone.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una zona con el código '{body.code}'")

    path = body.code
    if body.parent_zone_id:
        parent_result = await db.execute(
            select(Zone).where(Zone.id == str(body.parent_zone_id), Zone.warehouse_id == warehouse_id)
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona padre no encontrada")
        path = f"{parent.path} / {body.code}"

    zone = Zone(
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        parent_zone_id=str(body.parent_zone_id) if body.parent_zone_id else None,
        code=body.code,
        name=body.name,
        zone_type=body.zone_type.value,
        path=path,
        capacity_volume=body.capacity_volume,
        capacity_weight=body.capacity_weight,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return zone


async def list_zones(warehouse_id: str, db: AsyncSession, tenant_id: str) -> list[Zone]:
    await get_warehouse(warehouse_id, db, tenant_id)
    result = await db.execute(
        select(Zone).where(Zone.warehouse_id == warehouse_id, Zone.tenant_id == tenant_id)
        .order_by(Zone.path)
    )
    return list(result.scalars().all())


async def get_zone(zone_id: str, db: AsyncSession, tenant_id: str) -> Zone:
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.tenant_id == tenant_id)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona no encontrada")
    return zone


async def update_zone(zone_id: str, body: ZoneUpdate, db: AsyncSession, tenant_id: str) -> Zone:
    zone = await get_zone(zone_id, db, tenant_id)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        val = v.value if hasattr(v, "value") else v
        setattr(zone, k, val)
    await db.commit()
    await db.refresh(zone)
    return zone
