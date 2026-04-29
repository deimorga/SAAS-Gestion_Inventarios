from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.channel_allocation import ChannelAllocationCreate, ChannelAllocationResponse, ChannelAllocationUpdate
from app.services import channel_allocation as svc
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/channel-allocations", tags=["Channel Allocation"])


@router.post(
    "",
    response_model=ChannelAllocationResponse,
    status_code=201,
    summary="Definir cuota de inventario por canal",
    description=(
        "Reserva una cantidad de un producto en una zona para un canal de venta específico (WEB, POS, B2B, etc.). "
        "La cuota no descuenta el stock físico, pero permite que los sistemas de venta consulten la disponibilidad segmentada. "
        "Solo puede existir una cuota por combinación producto+zona+canal."
    ),
    responses={
        201: {"description": "Cuota creada"},
        409: {"description": "Ya existe una cuota para este canal/producto/zona"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_allocation(
    body: ChannelAllocationCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.create_allocation(body, db, auth.tenant_id)


@router.get(
    "",
    response_model=list[ChannelAllocationResponse],
    summary="Listar cuotas por canal",
    description="Retorna las cuotas de inventario definidas. Filtrable por producto, canal y estado.",
    responses={
        401: {"description": "No autenticado"},
    },
)
async def list_allocations(
    product_id: str | None = Query(None, description="Filtrar por UUID de producto"),
    channel: str | None = Query(None, description="Filtrar por canal (WEB, POS, B2B, etc.)"),
    is_active: bool = Query(True, description="Solo cuotas activas"),
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.list_allocations(db, auth.tenant_id, product_id, channel, is_active)


@router.patch(
    "/{allocation_id}",
    response_model=ChannelAllocationResponse,
    summary="Actualizar cuota de canal",
    description="Modifica la cantidad asignada, las notas o el estado activo de la cuota.",
    responses={
        404: {"description": "Cuota no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def update_allocation(
    allocation_id: str,
    body: ChannelAllocationUpdate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await svc.update_allocation(allocation_id, body, db, auth.tenant_id)


@router.delete(
    "/{allocation_id}",
    status_code=204,
    summary="Eliminar cuota de canal",
    description="Elimina permanentemente la cuota de canal especificada.",
    responses={
        204: {"description": "Cuota eliminada"},
        404: {"description": "Cuota no encontrada"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def delete_allocation(
    allocation_id: str,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await svc.delete_allocation(allocation_id, db, auth.tenant_id)
