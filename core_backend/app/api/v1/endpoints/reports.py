from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.reports import KardexResponse, LowStockResponse, SnapshotCreate, SnapshotResponse, ValuationResponse
from app.services import reports as svc

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/kardex",
    response_model=KardexResponse,
    summary="Kardex histórico de un producto",
    description=(
        "Retorna el histórico de movimientos de inventario para un producto, "
        "con balance acumulado por movimiento. Soporta filtros por almacén y rango de fechas. "
        "El campo `balance_after` refleja el saldo físico acumulado tras cada movimiento."
    ),
    responses={
        404: {"description": "Producto no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def kardex(
    product_id: str = Query(..., description="UUID del producto a consultar"),
    warehouse_id: str | None = Query(None, description="Filtrar por UUID de almacén"),
    date_from: datetime | None = Query(None, description="Fecha de inicio (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Fecha de fin (ISO 8601)"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Registros por página (máx 200)"),
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_kardex(db, auth.tenant_id, product_id, warehouse_id, date_from, date_to, page, page_size)


@router.get(
    "/valuation",
    response_model=ValuationResponse,
    summary="Valoración contable del inventario",
    description=(
        "Calcula la valoración total del inventario usando el Costo Promedio Ponderado (CPP) vigente. "
        "Retorna el total consolidado en moneda local y el detalle por producto."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def valuation(
    category_id: str | None = Query(None, description="Filtrar por UUID de categoría"),
    warehouse_id: str | None = Query(None, description="Filtrar por UUID de almacén"),
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_valuation(db, auth.tenant_id, category_id, warehouse_id)


@router.post(
    "/valuation/snapshots",
    summary="Crear snapshot contable de cierre",
    description=(
        "Lanza en segundo plano la captura del inventario valorado en el momento exacto de la llamada. "
        "Responde `202 Accepted` de inmediato; el proceso corre en background. "
        "Usar al cierre contable de cada período (mes/trimestre)."
    ),
    status_code=202,
    responses={
        202: {"description": "Snapshot en proceso"},
        401: {"description": "No autenticado"},
        403: {"description": "Solo tenant_admin o super_admin"},
    },
)
async def create_snapshot(
    body: SnapshotCreate,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    result = await svc.create_snapshot(db, auth.tenant_id, body, background_tasks)
    return JSONResponse(status_code=202, content=result)


@router.get(
    "/valuation/snapshots",
    response_model=list[SnapshotResponse],
    summary="Listar snapshots contables",
    description="Retorna los snapshots de valoración generados, opcionalmente filtrados por período (YYYY-MM).",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def list_snapshots(
    period: str | None = Query(None, description="Período en formato YYYY-MM (ej. 2026-04)"),
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.list_snapshots(db, auth.tenant_id, period)


@router.get(
    "/low-stock",
    response_model=LowStockResponse,
    summary="Alertas de stock bajo",
    description=(
        "Retorna productos cuya cantidad disponible (`available_qty`) es igual o inferior "
        "al punto de reorden (`reorder_point`) configurado en el producto. "
        "Ordenado por déficit descendente (mayor urgencia primero)."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def low_stock(
    warehouse_id: str | None = Query(None, description="Filtrar por UUID de almacén"),
    category_id: str | None = Query(None, description="Filtrar por UUID de categoría"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Registros por página (máx 200)"),
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_low_stock(db, auth.tenant_id, warehouse_id, category_id, page, page_size)
