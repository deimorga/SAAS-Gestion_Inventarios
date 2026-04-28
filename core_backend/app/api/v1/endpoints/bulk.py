from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, require_inventory_write
from app.schemas.bulk import BulkIssueRequest, BulkReceiptRequest, BulkResult, BulkTransferRequest
from app.services import bulk as svc

router = APIRouter(prefix="/bulk", tags=["Bulk Engine"])


@router.post(
    "/receipts",
    response_model=BulkResult,
    summary="Entrada masiva de mercancía",
    description=(
        "Procesa un lote de hasta 500 entradas de mercancía de forma independiente. "
        "Cada ítem se procesa en su propia transacción SQL: un fallo en un ítem no detiene el lote. "
        "La respuesta incluye el resultado individual (ok / error) de cada ítem con su índice. "
        "HTTP 200 si al menos un ítem tuvo éxito; HTTP 422 si el request es inválido."
    ),
    responses={
        200: {"description": "Lote procesado (puede haber fallos parciales)"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
        422: {"description": "Datos de entrada inválidos o lote vacío"},
    },
)
async def bulk_receipts(
    body: BulkReceiptRequest,
    auth: AuthContext = Depends(require_inventory_write),
):
    return await svc.bulk_receipts(auth.tenant_id, body, auth.user_id)


@router.post(
    "/issues",
    response_model=BulkResult,
    summary="Salida masiva de mercancía",
    description=(
        "Procesa un lote de hasta 500 salidas de mercancía. Igual que `/bulk/receipts`, "
        "cada ítem es atómico e independiente. Los ítems con stock insuficiente fallan "
        "individualmente sin afectar al resto del lote."
    ),
    responses={
        200: {"description": "Lote procesado (puede haber fallos parciales)"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
        422: {"description": "Datos de entrada inválidos o lote vacío"},
    },
)
async def bulk_issues(
    body: BulkIssueRequest,
    auth: AuthContext = Depends(require_inventory_write),
):
    return await svc.bulk_issues(auth.tenant_id, body, auth.user_id)


@router.post(
    "/transfers",
    response_model=BulkResult,
    summary="Transferencias masivas inter-almacén",
    description=(
        "Procesa un lote de hasta 500 transferencias entre zonas/almacenes. "
        "Cada transferencia es atómica (SALIDA + ENTRADA en una sola transacción SQL) "
        "e independiente de las demás en el lote."
    ),
    responses={
        200: {"description": "Lote procesado (puede haber fallos parciales)"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
        422: {"description": "Datos de entrada inválidos o lote vacío"},
    },
)
async def bulk_transfers(
    body: BulkTransferRequest,
    auth: AuthContext = Depends(require_inventory_write),
):
    return await svc.bulk_transfers(auth.tenant_id, body, auth.user_id)
