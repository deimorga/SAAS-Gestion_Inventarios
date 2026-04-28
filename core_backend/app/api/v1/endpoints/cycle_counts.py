from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.cycle_count import (
    CycleCountClose,
    CycleCountCreate,
    CycleCountItemResponse,
    CycleCountItemUpdate,
    CycleCountSessionResponse,
)
from app.services import cycle_count as svc

router = APIRouter(prefix="/cycle-counts", tags=["Inventario Cíclico"])


@router.post(
    "",
    response_model=CycleCountSessionResponse,
    status_code=201,
    summary="Iniciar sesión de conteo cíclico",
    description=(
        "Crea una sesión de conteo para un almacén. Al crear la sesión, el sistema toma una "
        "fotografía de las cantidades físicas actuales (`physical_qty`) de todos los productos "
        "del almacén como `expected_qty`. El conteo registra las diferencias entre lo esperado "
        "y lo encontrado físicamente."
    ),
    responses={
        201: {"description": "Sesión creada con snapshot de stock_balances"},
        404: {"description": "Almacén no encontrado o inactivo"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_session(
    body: CycleCountCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    return await svc.create_session(db, auth.tenant_id, body)


@router.get(
    "",
    response_model=list[CycleCountSessionResponse],
    summary="Listar sesiones de conteo",
    description="Retorna sesiones de conteo del tenant, opcionalmente filtradas por estado (OPEN, CLOSED).",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def list_sessions(
    status: str | None = Query(None, description="Filtrar por estado: OPEN | CLOSED"),
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.list_sessions(db, auth.tenant_id, status)


@router.get(
    "/{session_id}",
    response_model=CycleCountSessionResponse,
    summary="Obtener detalle de una sesión de conteo",
    description=(
        "Retorna la sesión con todos sus ítems, incluyendo `expected_qty`, `counted_qty` y "
        "`variance` (= counted − expected) para cada producto. Los ítems aún no contados "
        "tienen `counted_qty` y `variance` como null."
    ),
    responses={
        404: {"description": "Sesión no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_session(
    session_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_session(db, auth.tenant_id, session_id)


@router.patch(
    "/{session_id}/items/{item_id}",
    response_model=CycleCountItemResponse,
    summary="Registrar cantidad contada para un ítem",
    description=(
        "Actualiza la `counted_qty` de un ítem de conteo. Solo disponible en sesiones OPEN. "
        "Puede llamarse múltiples veces para el mismo ítem — el último valor registrado prevalece."
    ),
    responses={
        404: {"description": "Sesión o ítem no encontrado"},
        409: {"description": "La sesión ya está cerrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def record_count(
    session_id: str,
    item_id: str,
    body: CycleCountItemUpdate,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    return await svc.record_count(db, auth.tenant_id, session_id, item_id, body)


@router.post(
    "/{session_id}/close",
    response_model=CycleCountSessionResponse,
    summary="Cerrar sesión de conteo",
    description=(
        "Cierra la sesión de conteo. Si la sesión fue creada con `apply_adjustments=true`, "
        "el sistema genera automáticamente una transacción de tipo `ADJUSTMENT` en `inventory_ledger` "
        "por cada ítem cuya `counted_qty` difiera de `expected_qty`. "
        "Los ítems sin `counted_qty` se omiten del ajuste."
    ),
    responses={
        200: {"description": "Sesión cerrada; ajustes aplicados si apply_adjustments=true"},
        409: {"description": "La sesión ya está cerrada"},
        404: {"description": "Sesión no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def close_session(
    session_id: str,
    body: CycleCountClose,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    return await svc.close_session(db, auth.tenant_id, session_id, body)
