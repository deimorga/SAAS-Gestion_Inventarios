from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.reservation import ReservationConfirm, ReservationCreate, ReservationResponse
from app.services import reservation as svc

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=201,
    summary="Crear reserva de stock",
    description=(
        "Reserva temporalmente stock disponible para uno o más productos. "
        "Reduce `available_qty` e incrementa `reserved_qty` en `stock_balances` usando OCC. "
        "Si no se envía `expires_at`, se aplica el TTL configurado en el tenant (`RESERVATION_TTL_MINUTES`). "
        "La reserva expira automáticamente en background al alcanzar `expires_at`."
    ),
    responses={
        409: {"description": "Stock insuficiente o conflicto de concurrencia"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_reservation(
    body: ReservationCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    return await svc.create_reservation(db, auth.tenant_id, body)


@router.get(
    "",
    response_model=list[ReservationResponse],
    summary="Listar reservas",
    description="Retorna reservas del tenant, opcionalmente filtradas por estado (ACTIVE, COMPLETED, CANCELLED, EXPIRED).",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def list_reservations(
    status: str | None = Query(None, description="Filtrar por estado: ACTIVE | COMPLETED | CANCELLED | EXPIRED"),
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.list_reservations(db, auth.tenant_id, status)


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Obtener detalle de una reserva",
    description="Retorna la reserva con el detalle completo de sus ítems.",
    responses={
        404: {"description": "Reserva no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def get_reservation(
    reservation_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db=Depends(get_auth_db),
):
    return await svc.get_reservation(db, auth.tenant_id, reservation_id)


@router.post(
    "/{reservation_id}/confirm",
    response_model=ReservationResponse,
    summary="Confirmar reserva (convertir en salida)",
    description=(
        "Convierte una reserva ACTIVE en una salida real de inventario. "
        "Disminuye `physical_qty` por la cantidad confirmada y libera el excedente reservado a `available_qty`. "
        "Registra un movimiento `ISSUE` en `inventory_ledger` por cada ítem. "
        "La cantidad confirmada puede ser menor a la reservada (el cliente compró menos)."
    ),
    responses={
        409: {"description": "La reserva no está en estado ACTIVE"},
        404: {"description": "Reserva no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def confirm_reservation(
    reservation_id: str,
    body: ReservationConfirm,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    return await svc.confirm_reservation(db, auth.tenant_id, reservation_id, body)


@router.post(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
    summary="Cancelar reserva explícitamente",
    description=(
        "Cancela una reserva ACTIVE y devuelve el stock reservado a `available_qty`. "
        "Úsese cuando el cliente abandona el carrito o la cotización es rechazada. "
        "Las reservas también se cancelan automáticamente al vencer (`expires_at`)."
    ),
    responses={
        409: {"description": "La reserva no está en estado ACTIVE"},
        404: {"description": "Reserva no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def cancel_reservation(
    reservation_id: str,
    auth: AuthContext = Depends(require_inventory_write),
    db=Depends(get_auth_db),
):
    return await svc.cancel_reservation(db, auth.tenant_id, reservation_id)
