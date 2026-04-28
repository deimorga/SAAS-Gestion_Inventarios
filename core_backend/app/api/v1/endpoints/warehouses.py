from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.common import PaginatedResponse
from app.schemas.warehouse import WarehouseCreate, WarehouseListItem, WarehouseResponse, WarehouseUpdate, ZoneCreate, ZoneResponse, ZoneUpdate
from app.services.audit import log_action
from app.services.warehouse import (
    create_warehouse,
    create_zone,
    get_warehouse,
    get_zone,
    list_warehouses,
    list_zones,
    update_warehouse,
    update_zone,
)

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("", response_model=PaginatedResponse)
async def get_warehouses(
    is_active: bool = Query(True),
    is_virtual: bool | None = Query(None),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    items = await list_warehouses(db, auth.tenant_id, is_active, is_virtual)
    return PaginatedResponse(
        data=[WarehouseListItem.model_validate(w) for w in items],
        pagination={"page": 1, "page_size": len(items), "total_items": len(items), "total_pages": 1},
    )


@router.post("", response_model=WarehouseResponse, status_code=201)
async def add_warehouse(
    body: WarehouseCreate,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    wh = await create_warehouse(body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="warehouses", entity_id=str(wh.id),
        action="CREATE", new_values={"code": wh.code, "name": wh.name},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return wh


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
async def get_warehouse_detail(
    warehouse_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_warehouse(warehouse_id, db, auth.tenant_id)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
async def patch_warehouse(
    warehouse_id: str,
    body: WarehouseUpdate,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    updated = await update_warehouse(warehouse_id, body, db, auth.tenant_id)
    changes = body.model_dump(exclude_none=True)
    if changes:
        await log_action(
            db=db, tenant_id=auth.tenant_id, entity="warehouses", entity_id=warehouse_id,
            action="UPDATE", new_values=changes,
            performed_by={"type": "user", "id": auth.user_id},
            ip_address=request.client.host if request.client else None,
        )
    return updated


@router.get("/{warehouse_id}/zones", response_model=list[ZoneResponse])
async def get_zones(
    warehouse_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_zones(warehouse_id, db, auth.tenant_id)


@router.post("/{warehouse_id}/zones", response_model=ZoneResponse, status_code=201)
async def add_zone(
    warehouse_id: str,
    body: ZoneCreate,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    zone = await create_zone(warehouse_id, body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="zones", entity_id=str(zone.id),
        action="CREATE", new_values={"code": zone.code, "zone_type": zone.zone_type},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return zone


@router.get("/zones/{zone_id}", response_model=ZoneResponse)
async def get_zone_detail(
    zone_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_zone(zone_id, db, auth.tenant_id)


@router.patch("/zones/{zone_id}", response_model=ZoneResponse)
async def patch_zone(
    zone_id: str,
    body: ZoneUpdate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await update_zone(zone_id, body, db, auth.tenant_id)
