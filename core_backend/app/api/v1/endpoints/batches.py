from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.batch import BatchCreate, BatchResponse, SerialNumberBulkCreate, SerialNumberResponse, SerialStatusResponse
from app.services import batch as svc
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Lotes y Seriales"])
serials_router = APIRouter(tags=["Lotes y Seriales"])


@router.post(
    "/batches",
    response_model=BatchResponse,
    status_code=201,
    summary="Crear lote",
    description=(
        "Registra un lote de fabricación o recepción para un producto con `track_lots=true`. "
        "El `batch_number` debe ser único por producto en el tenant. "
        "La `expiry_date` es requerida para productos con `track_expiry=true`."
    ),
    responses={
        201: {"description": "Lote creado"},
        409: {"description": "Número de lote duplicado para este producto"},
        422: {"description": "El producto no tiene trazabilidad de lotes habilitada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_batch(
    body: BatchCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.create_batch(body, db, auth.tenant_id)


@router.get(
    "/batches",
    response_model=list[BatchResponse],
    summary="Listar lotes",
    description="Retorna los lotes registrados. Filtrable por producto.",
    responses={
        401: {"description": "No autenticado"},
    },
)
async def list_batches(
    product_id: str | None = Query(None, description="Filtrar por UUID de producto"),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.list_batches(db, auth.tenant_id, product_id)


@router.get(
    "/batches/{batch_id}",
    response_model=BatchResponse,
    summary="Detalle de lote",
    description="Retorna el detalle completo de un lote, incluyendo fechas de fabricación y vencimiento.",
    responses={
        404: {"description": "Lote no encontrado"},
        401: {"description": "No autenticado"},
    },
)
async def get_batch(
    batch_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.get_batch(batch_id, db, auth.tenant_id)


@router.post(
    "/batches/{batch_id}/serials",
    response_model=list[SerialNumberResponse],
    status_code=201,
    summary="Registrar seriales en el lote",
    description=(
        "Agrega números de serie al lote. El producto debe tener `track_serials=true`. "
        "Cada serial debe ser único dentro del tenant. Máximo 500 seriales por petición."
    ),
    responses={
        201: {"description": "Seriales registrados"},
        404: {"description": "Lote no encontrado"},
        409: {"description": "Uno o más seriales ya existen en el tenant"},
        422: {"description": "El producto no tiene trazabilidad de seriales habilitada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def add_serials(
    batch_id: str,
    body: SerialNumberBulkCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.add_serials(batch_id, body, db, auth.tenant_id)


@router.get(
    "/batches/{batch_id}/serials",
    response_model=list[SerialNumberResponse],
    summary="Listar seriales del lote",
    description="Retorna todos los seriales registrados en el lote con su estado (AVAILABLE / CONSUMED / RESERVED).",
    responses={
        404: {"description": "Lote no encontrado"},
        401: {"description": "No autenticado"},
    },
)
async def list_serials(
    batch_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.list_serials(batch_id, db, auth.tenant_id)


@serials_router.get(
    "/serials/{serial_number}/status",
    response_model=SerialStatusResponse,
    summary="Consultar estado de serial",
    description=(
        "Verifica si un número de serie existe y retorna su estado actual: "
        "`AVAILABLE` (disponible para issue), `RESERVED` (en reserva activa), `CONSUMED` (ya fue emitido). "
        "Útil para validar el serial antes de procesar una salida."
    ),
    responses={
        404: {"description": "Serial no encontrado en este tenant"},
        401: {"description": "No autenticado"},
    },
)
async def get_serial_status(
    serial_number: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.get_serial_status(serial_number, db, auth.tenant_id)
