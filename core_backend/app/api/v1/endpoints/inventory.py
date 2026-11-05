from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    AdjustmentRequest,
    IssueRequest,
    ReceiptRequest,
    RepackRequest,
    TransactionResponse,
    TransferRequest,
)
from app.services.inventory import (
    process_adjustment,
    process_issue,
    process_receipt,
    process_repack,
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


@transactions_router.post(
    "/repacks",
    response_model=TransactionResponse,
    status_code=201,
    summary="Re-empaque (RF-021)",
    description=(
        "Convierte una presentación de producto en otra dentro del mismo almacén/zona. "
        "Consume los `source_items` (genera movimiento ISSUE) y produce los `target_items` (genera movimiento RECEIPT). "
        "Toda la operación es atómica: si falla cualquier ítem se revierte todo."
    ),
    responses={
        201: {"description": "Re-empaque registrado"},
        404: {"description": "Producto, almacén o zona no encontrado"},
        409: {"description": "Stock insuficiente en algún ítem origen"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def repack(
    body: RepackRequest,
    request: Request,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await process_repack(body, db, auth.tenant_id, created_by=auth.user_id)


@stock_router.get(
    "/balances",
    response_model=PaginatedResponse,
    summary="Consultar saldos de stock",
    description=(
        "Retorna los saldos actuales de inventario por producto/zona/bin/lote/proveedor. "
        "Cada registro muestra `physical_qty`, `reserved_qty` y `available_qty` (= physical - reserved), "
        "y la ubicación exacta (`bin_id`, `bin_code`, `bin_name`) y el proveedor del lote (`supplier_id`) "
        "cuando los hay. Filtros opcionales: `lot_number` (¿dónde está el lote X?), `bin_id` "
        "(¿qué hay en el estante 3?) y `supplier_id`."
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
    lot_number: str | None = Query(None, description="Filtrar por número de lote"),
    bin_id: UUID | None = Query(None, description="Filtrar por UUID de ubicación (bin)"),
    supplier_id: UUID | None = Query(None, description="Filtrar por UUID de proveedor del lote"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Registros por página (máx 200)"),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await query_stock_balances(
        db, auth.tenant_id, product_id, warehouse_id, zone_id, page, page_size,
        lot_number=lot_number, bin_id=bin_id, supplier_id=supplier_id,
    )


@ledger_router.get(
    "",
    response_model=PaginatedResponse,
    summary="Consultar ledger de movimientos",
    description=(
        "Retorna el historial inmutable de movimientos de inventario. "
        "El ledger es append-only: ninguna entrada puede ser modificada o eliminada. "
        "Cada entrada devuelve lote, ubicación (`bin_id`, `bin_code`, `bin_name`), proveedor (`supplier_id`) "
        "y, si viene de una entrada, su consecutivo (`document_number`, ej. E-000058). "
        "Filtros: producto, almacén, transacción, lote, zona, bin, proveedor, `reference_id` "
        "(ej. la orden de servicio), `document_number` y rango de fechas `date_from`/`date_to` "
        "(YYYY-MM-DD, ambos inclusivos)."
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
    lot_number: str | None = Query(None, description="Filtrar por número de lote"),
    zone_id: UUID | None = Query(None, description="Filtrar por UUID de zona"),
    bin_id: UUID | None = Query(None, description="Filtrar por UUID de ubicación (bin)"),
    supplier_id: UUID | None = Query(None, description="Filtrar por UUID de proveedor"),
    reference_id: str | None = Query(None, description="Filtrar por referencia (ej. orden de servicio OT-2026-00892)"),
    document_number: str | None = Query(None, description="Filtrar por consecutivo de entrada (ej. E-000058)"),
    date_from: date | None = Query(None, description="Desde esta fecha, inclusive (YYYY-MM-DD, UTC)"),
    date_to: date | None = Query(None, description="Hasta esta fecha, inclusive (YYYY-MM-DD, UTC)"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Registros por página (máx 200)"),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await query_ledger(
        db, auth.tenant_id, product_id, warehouse_id, transaction_id, page, page_size,
        lot_number=lot_number, zone_id=zone_id, bin_id=bin_id, supplier_id=supplier_id,
        reference_id=reference_id, document_number=document_number,
        date_from=date_from, date_to=date_to,
    )
