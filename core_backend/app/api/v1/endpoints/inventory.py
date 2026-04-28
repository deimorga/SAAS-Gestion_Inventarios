from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    AdjustmentRequest,
    IssueRequest,
    ReceiptRequest,
    TransactionResponse,
    TransferRequest,
)
from app.services.inventory import (
    process_adjustment,
    process_issue,
    process_receipt,
    process_transfer,
    query_ledger,
    query_stock_balances,
)

transactions_router = APIRouter(prefix="/transactions", tags=["Inventory Motor"])
stock_router = APIRouter(prefix="/stock", tags=["Stock"])
ledger_router = APIRouter(prefix="/ledger", tags=["Ledger"])


@transactions_router.post("/receipts", response_model=TransactionResponse, status_code=201)
async def receipt(
    body: ReceiptRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_receipt(body, db, auth.tenant_id, created_by=auth.user_id)


@transactions_router.post("/issues", response_model=TransactionResponse, status_code=201)
async def issue(
    body: IssueRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_issue(body, db, auth.tenant_id, created_by=auth.user_id)


@transactions_router.post("/transfers", response_model=TransactionResponse, status_code=201)
async def transfer(
    body: TransferRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_transfer(body, db, auth.tenant_id, created_by=auth.user_id)


@transactions_router.post("/adjustments", response_model=TransactionResponse, status_code=201)
async def adjustment(
    body: AdjustmentRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_adjustment(body, db, auth.tenant_id, created_by=auth.user_id)


@stock_router.get("/balances", response_model=PaginatedResponse)
async def stock_balances(
    product_id: str | None = Query(None),
    warehouse_id: str | None = Query(None),
    zone_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await query_stock_balances(db, auth.tenant_id, product_id, warehouse_id, zone_id, page, page_size)


@ledger_router.get("", response_model=PaginatedResponse)
async def ledger(
    product_id: str | None = Query(None),
    warehouse_id: str | None = Query(None),
    transaction_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await query_ledger(db, auth.tenant_id, product_id, warehouse_id, transaction_id, page, page_size)
