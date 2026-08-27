from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_super_admin
from app.core.database import AsyncSessionLocal, set_tenant_context
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import AdjustmentRequest, ReceiptRequest, TransactionResponse
from app.schemas.warehouse import WarehouseCreate, WarehouseResponse, ZoneCreate, ZoneResponse
from app.services import inventory as inv_service
from app.services import warehouse as wh_service

router = APIRouter(tags=["Admin — Stock"])


async def _session(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        yield session


@router.get(
    "/tenants/{tenant_id}/stock",
    response_model=PaginatedResponse,
    summary="Saldos de stock de un tenant",
)
async def admin_stock_balances(
    tenant_id: str,
    product_id: str | None = Query(None),
    warehouse_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await inv_service.query_stock_balances(
            db=session,
            tenant_id=tenant_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            page=page,
            page_size=page_size,
        )


@router.post(
    "/tenants/{tenant_id}/stock/receipts",
    response_model=TransactionResponse,
    status_code=201,
    summary="Registrar entrada de stock para un tenant",
)
async def admin_stock_receipt(
    tenant_id: str,
    body: ReceiptRequest,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await inv_service.process_receipt(body=body, db=session, tenant_id=tenant_id)


@router.post(
    "/tenants/{tenant_id}/stock/adjustments",
    response_model=TransactionResponse,
    status_code=201,
    summary="Ajustar stock de un tenant",
)
async def admin_stock_adjustment(
    tenant_id: str,
    body: AdjustmentRequest,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await inv_service.process_adjustment(body=body, db=session, tenant_id=tenant_id)


@router.get(
    "/tenants/{tenant_id}/warehouses",
    summary="Listar almacenes de un tenant",
)
async def admin_list_warehouses(
    tenant_id: str,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        warehouses = await wh_service.list_warehouses(db=session, tenant_id=tenant_id)
        return [
            {
                "id": str(w.id),
                "code": w.code,
                "name": w.name,
                "location_address": w.location_address,
                "is_virtual": w.is_virtual,
                "is_active": w.is_active,
            }
            for w in warehouses
        ]


@router.get(
    "/tenants/{tenant_id}/warehouses/{warehouse_id}/zones",
    summary="Listar zonas de un almacén",
)
async def admin_list_zones(
    tenant_id: str,
    warehouse_id: str,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        zones = await wh_service.list_zones(warehouse_id=warehouse_id, db=session, tenant_id=tenant_id)
        return [
            {"id": str(z.id), "code": z.code, "name": z.name, "zone_type": z.zone_type}
            for z in zones
        ]


@router.post(
    "/tenants/{tenant_id}/warehouses",
    response_model=WarehouseResponse,
    status_code=201,
    summary="Crear almacén para un tenant",
    description=(
        "Crea un almacén en el tenant indicado. Si `is_virtual=false` se auto-crean las zonas "
        "`RECEIVING`, `DISPATCH` y `QUARANTINE`, dejando el almacén listo para recibir stock."
    ),
)
async def admin_create_warehouse(
    tenant_id: str,
    body: WarehouseCreate,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await wh_service.create_warehouse(body=body, db=session, tenant_id=tenant_id)


@router.post(
    "/tenants/{tenant_id}/warehouses/{warehouse_id}/zones",
    response_model=ZoneResponse,
    status_code=201,
    summary="Crear zona en un almacén de un tenant",
)
async def admin_create_zone(
    tenant_id: str,
    warehouse_id: str,
    body: ZoneCreate,
    _auth: AuthContext = Depends(require_super_admin),
):
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, tenant_id)
        return await wh_service.create_zone(
            warehouse_id=warehouse_id, body=body, db=session, tenant_id=tenant_id
        )
