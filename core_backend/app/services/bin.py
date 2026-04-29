from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bin import Bin, LocationLock
from app.models.zone import Zone
from app.schemas.bin import BinCreate, BinResponse, BinUpdate, LocationLockCreate, LocationLockResponse


async def _get_zone_or_404(db: AsyncSession, zone_id: str, warehouse_id: str, tenant_id: str) -> Zone:
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.warehouse_id == warehouse_id, Zone.tenant_id == tenant_id)
    )
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona no encontrada")
    return zone


async def _get_bin_or_404(db: AsyncSession, bin_id: str, tenant_id: str) -> Bin:
    result = await db.execute(
        select(Bin).where(Bin.id == bin_id, Bin.tenant_id == tenant_id)
    )
    b = result.scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bin no encontrado")
    return b


async def list_bins(warehouse_id: str, zone_id: str, db: AsyncSession, tenant_id: str) -> list[BinResponse]:
    await _get_zone_or_404(db, zone_id, warehouse_id, tenant_id)
    result = await db.execute(
        select(Bin).where(Bin.zone_id == zone_id, Bin.tenant_id == tenant_id).order_by(Bin.code)
    )
    return [BinResponse.model_validate(b) for b in result.scalars().all()]


async def create_bin(warehouse_id: str, zone_id: str, body: BinCreate, db: AsyncSession, tenant_id: str) -> BinResponse:
    await _get_zone_or_404(db, zone_id, warehouse_id, tenant_id)

    dup = await db.execute(
        select(Bin).where(Bin.zone_id == zone_id, Bin.code == body.code)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El código '{body.code}' ya existe en esta zona")

    now = datetime.now(timezone.utc)
    b = Bin(
        id=str(uuid4()),
        tenant_id=tenant_id,
        zone_id=zone_id,
        code=body.code,
        name=body.name,
        max_weight_kg=body.max_weight_kg,
        max_volume_m3=body.max_volume_m3,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return BinResponse.model_validate(b)


async def update_bin(bin_id: str, body: BinUpdate, db: AsyncSession, tenant_id: str) -> BinResponse:
    b = await _get_bin_or_404(db, bin_id, tenant_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(b, field, value)
    b.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(b)
    return BinResponse.model_validate(b)


async def deactivate_bin(bin_id: str, db: AsyncSession, tenant_id: str) -> None:
    b = await _get_bin_or_404(db, bin_id, tenant_id)
    b.is_active = False
    b.updated_at = datetime.now(timezone.utc)
    await db.commit()


# ── Location Locks (RF-015) ───────────────────────────────────────────────────

async def lock_bin(bin_id: str, body: LocationLockCreate, db: AsyncSession, tenant_id: str, locked_by: str) -> LocationLockResponse:
    b = await _get_bin_or_404(db, bin_id, tenant_id)

    existing = await db.execute(
        select(LocationLock).where(LocationLock.bin_id == b.id, LocationLock.is_active.is_(True))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El bin ya tiene un bloqueo activo")

    now = datetime.now(timezone.utc)
    lock = LocationLock(
        id=str(uuid4()),
        tenant_id=tenant_id,
        bin_id=bin_id,
        reason=body.reason,
        locked_by=locked_by,
        locked_at=now,
        is_active=True,
    )
    db.add(lock)
    await db.commit()
    await db.refresh(lock)
    return LocationLockResponse.model_validate(lock)


async def unlock_bin(bin_id: str, db: AsyncSession, tenant_id: str) -> None:
    b = await _get_bin_or_404(db, bin_id, tenant_id)
    result = await db.execute(
        select(LocationLock).where(LocationLock.bin_id == b.id, LocationLock.is_active.is_(True))
    )
    lock = result.scalar_one_or_none()
    if lock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay bloqueo activo en este bin")
    lock.is_active = False
    lock.unlocked_at = datetime.now(timezone.utc)
    await db.commit()


async def get_bin_lock(bin_id: str, db: AsyncSession, tenant_id: str) -> LocationLockResponse | None:
    b = await _get_bin_or_404(db, bin_id, tenant_id)
    result = await db.execute(
        select(LocationLock).where(LocationLock.bin_id == b.id, LocationLock.is_active.is_(True))
    )
    lock = result.scalar_one_or_none()
    return LocationLockResponse.model_validate(lock) if lock else None
