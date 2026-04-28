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


@transactions_router.post(
    "/receipts",
    response_model=TransactionResponse,
    status_code=201,
    summary="Registrar entrada de mercancía",
    description=(
        "Crea una transacción de tipo RECEIPT. Por cada ítem: "
        "incrementa `physical_qty` y `available_qty` en `stock_balances`, "
        "recalcula el CPP (Costo Promedio Ponderado) en el producto, "
        "y registra un movimiento `RECEIPT` en `inventory_ledger`. "
        "Para devoluciones de cliente, usar `reference_type=RETURN_IN`."
    ),
    responses={
        201: {"description": "Transacción registrada"},
        404: {"description": "Almacén, zona o producto no encontrado"},
        409: {"description": "Almacén o zona inactivos"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def receipt(
    body: ReceiptRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_receipt(body, db, auth.tenant_id, created_by=auth.user_id)


@transactions_router.post(
    "/issues",
    response_model=TransactionResponse,
    status_code=201,
    summary="Registrar salida de mercancía",
    description=(
        "Crea una transacción de tipo ISSUE. Valida stock suficiente para **todos** los ítems "
        "antes de escribir (pre-validación). Aplica OCC con reintentos sobre `stock_balances`. "
        "Para bajas y mermas, usar `reason_code=SCRAP_LOSS` — registra `movement_type=SCRAP` en el ledger."
    ),
    responses={
        201: {"description": "Transacción registrada"},
        409: {"description": "Stock insuficiente para uno o más ítems, o conflicto de concurrencia"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def issue(
    body: IssueRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_issue(body, db, auth.tenant_id, created_by=auth.user_id)


@transactions_router.post(
    "/transfers",
    response_model=TransactionResponse,
    status_code=201,
    summary="Transferencia inter-almacén",
    description=(
        "Mueve stock de una zona origen a una zona destino en una transacción ACID. "
        "Genera exactamente dos entradas en `inventory_ledger`: `TRANSFER_OUT` (origen) y `TRANSFER_IN` (destino). "
        "Origen y destino pueden estar en el mismo almacén o en almacenes distintos."
    ),
    responses={
        201: {"description": "Transferencia registrada"},
        409: {"description": "Stock insuficiente en origen o conflicto de concurrencia"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def transfer(
    body: TransferRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_transfer(body, db, auth.tenant_id, created_by=auth.user_id)


@transactions_router.post(
    "/adjustments",
    response_model=TransactionResponse,
    status_code=201,
    summary="Ajuste por conteo físico",
    description=(
        "Ajusta el saldo de un producto en una zona a una cantidad exacta (`new_qty`). "
        "El delta (positivo o negativo) se calcula como `new_qty - physical_qty_actual`. "
        "Registra movimiento `ADJUSTMENT` en ledger. Usado tras inventarios físicos."
    ),
    responses={
        201: {"description": "Ajuste registrado"},
        404: {"description": "Producto, almacén o zona no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def adjustment(
    body: AdjustmentRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_adjustment(body, db, auth.tenant_id, created_by=auth.user_id)


@stock_router.get(
    "/balances",
    response_model=PaginatedResponse,
    summary="Consultar saldos de stock",
    description=(
        "Retorna los saldos actuales de inventario por producto/zona/lote. "
        "Cada registro muestra `physical_qty`, `reserved_qty` y `available_qty` (= physical - reserved)."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def stock_balances(
    product_id: str | None = Query(None, description="Filtrar por UUID de producto"),
    warehouse_id: str | None = Query(None, description="Filtrar por UUID de almacén"),
    zone_id: str | None = Query(None, description="Filtrar por UUID de zona"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Registros por página (máx 200)"),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await query_stock_balances(db, auth.tenant_id, product_id, warehouse_id, zone_id, page, page_size)


@ledger_router.get(
    "",
    response_model=PaginatedResponse,
    summary="Consultar ledger de movimientos",
    description=(
        "Retorna el historial inmutable de movimientos de inventario. "
        "El ledger es append-only: ninguna entrada puede ser modificada o eliminada. "
        "Soporta filtros por producto, almacén y transacción."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def ledger(
    product_id: str | None = Query(None, description="Filtrar por UUID de producto"),
    warehouse_id: str | None = Query(None, description="Filtrar por UUID de almacén"),
    transaction_id: str | None = Query(None, description="Filtrar por UUID de transacción"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Registros por página (máx 200)"),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await query_ledger(db, auth.tenant_id, product_id, warehouse_id, transaction_id, page, page_size)
