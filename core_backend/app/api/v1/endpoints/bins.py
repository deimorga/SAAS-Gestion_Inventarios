from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_auth_db, require_inventory_read, require_inventory_write
from app.schemas.bin import BinCreate, BinResponse, BinUpdate, LocationLockCreate, LocationLockResponse
from app.services import bin as bin_svc
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Zonificación y Bloqueos"])


@router.get(
    "/warehouses/{warehouse_id}/zones/{zone_id}/bins",
    response_model=list[BinResponse],
    summary="Listar bins de la zona",
    description="Retorna los bins (ubicaciones físicas) registrados en la zona del almacén.",
    responses={
        404: {"description": "Zona o almacén no encontrado"},
        401: {"description": "No autenticado"},
    },
)
async def list_bins(
    warehouse_id: str,
    zone_id: str,
    auth: AuthContext = Depends(require_inventory_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await bin_svc.list_bins(warehouse_id, zone_id, db, auth.tenant_id)


@router.post(
    "/warehouses/{warehouse_id}/zones/{zone_id}/bins",
    response_model=BinResponse,
    status_code=201,
    summary="Crear bin en la zona",
    description=(
        "Crea una ubicación física (bin/slot) dentro de la zona. "
        "El `code` debe ser único dentro de la zona. "
        "Opcionalmente se puede definir capacidad máxima de peso y volumen."
    ),
    responses={
        201: {"description": "Bin creado"},
        404: {"description": "Zona o almacén no encontrado"},
        409: {"description": "Código de bin duplicado en la zona"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def create_bin(
    warehouse_id: str,
    zone_id: str,
    body: BinCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await bin_svc.create_bin(warehouse_id, zone_id, body, db, auth.tenant_id)


@router.patch(
    "/warehouses/bins/{bin_id}",
    response_model=BinResponse,
    summary="Actualizar bin",
    description="Actualiza el nombre, capacidades o estado activo del bin.",
    responses={
        404: {"description": "Bin no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def update_bin(
    bin_id: str,
    body: BinUpdate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await bin_svc.update_bin(bin_id, body, db, auth.tenant_id)


@router.delete(
    "/warehouses/bins/{bin_id}",
    status_code=204,
    summary="Desactivar bin (soft delete)",
    description="Marca el bin como inactivo. No elimina el historial de inventario asociado.",
    responses={
        204: {"description": "Bin desactivado"},
        404: {"description": "Bin no encontrado"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def deactivate_bin(
    bin_id: str,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await bin_svc.deactivate_bin(bin_id, db, auth.tenant_id)


# ── Location Locks (RF-015) ───────────────────────────────────────────────────

@router.post(
    "/warehouses/bins/{bin_id}/locks",
    response_model=LocationLockResponse,
    status_code=201,
    summary="Bloquear bin",
    description=(
        "Bloquea el bin para impedir movimientos de inventario. "
        "Solo puede existir un bloqueo activo por bin a la vez. "
        "El motivo queda registrado en el historial de bloqueos."
    ),
    responses={
        201: {"description": "Bloqueo creado"},
        404: {"description": "Bin no encontrado"},
        409: {"description": "El bin ya tiene un bloqueo activo"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def lock_bin(
    bin_id: str,
    body: LocationLockCreate,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    return await bin_svc.lock_bin(bin_id, body, db, auth.tenant_id, auth.user_id)


@router.delete(
    "/warehouses/bins/{bin_id}/locks",
    status_code=204,
    summary="Desbloquear bin",
    description="Elimina el bloqueo activo del bin, permitiendo nuevamente movimientos de inventario.",
    responses={
        204: {"description": "Bin desbloqueado"},
        404: {"description": "Bin sin bloqueo activo"},
        401: {"description": "No autenticado"},
        403: {"description": "Sin permisos suficientes"},
    },
)
async def unlock_bin(
    bin_id: str,
    auth: AuthContext = Depends(require_inventory_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await bin_svc.unlock_bin(bin_id, db, auth.tenant_id)
