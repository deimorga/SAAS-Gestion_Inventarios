from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel_allocation import ChannelAllocation
from app.schemas.channel_allocation import (
    ChannelAllocationCreate,
    ChannelAllocationResponse,
    ChannelAllocationUpdate,
)


async def create_allocation(body: ChannelAllocationCreate, db: AsyncSession, tenant_id: str) -> ChannelAllocationResponse:
    dup = await db.execute(
        select(ChannelAllocation).where(
            ChannelAllocation.product_id == str(body.product_id),
            ChannelAllocation.zone_id == str(body.zone_id),
            ChannelAllocation.channel == body.channel,
            ChannelAllocation.tenant_id == tenant_id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cuota para el canal '{body.channel}' en ese producto/zona",
        )

    now = datetime.now(timezone.utc)
    alloc = ChannelAllocation(
        id=str(uuid4()),
        tenant_id=tenant_id,
        product_id=str(body.product_id),
        zone_id=str(body.zone_id),
        channel=body.channel,
        allocated_qty=body.allocated_qty,
        notes=body.notes,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(alloc)
    await db.commit()
    await db.refresh(alloc)
    return ChannelAllocationResponse.model_validate(alloc)


async def list_allocations(
    db: AsyncSession,
    tenant_id: str,
    product_id: str | None = None,
    channel: str | None = None,
    is_active: bool = True,
) -> list[ChannelAllocationResponse]:
    query = select(ChannelAllocation).where(ChannelAllocation.tenant_id == tenant_id)
    if product_id:
        query = query.where(ChannelAllocation.product_id == product_id)
    if channel:
        query = query.where(ChannelAllocation.channel == channel)
    if is_active is not None:
        query = query.where(ChannelAllocation.is_active.is_(is_active))
    query = query.order_by(ChannelAllocation.channel, ChannelAllocation.created_at)
    result = await db.execute(query)
    return [ChannelAllocationResponse.model_validate(a) for a in result.scalars().all()]


async def update_allocation(alloc_id: str, body: ChannelAllocationUpdate, db: AsyncSession, tenant_id: str) -> ChannelAllocationResponse:
    result = await db.execute(
        select(ChannelAllocation).where(ChannelAllocation.id == alloc_id, ChannelAllocation.tenant_id == tenant_id)
    )
    alloc = result.scalar_one_or_none()
    if alloc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuota de canal no encontrada")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(alloc, field, value)
    alloc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(alloc)
    return ChannelAllocationResponse.model_validate(alloc)


async def delete_allocation(alloc_id: str, db: AsyncSession, tenant_id: str) -> None:
    result = await db.execute(
        select(ChannelAllocation).where(ChannelAllocation.id == alloc_id, ChannelAllocation.tenant_id == tenant_id)
    )
    alloc = result.scalar_one_or_none()
    if alloc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuota de canal no encontrada")
    await db.delete(alloc)
    await db.commit()
