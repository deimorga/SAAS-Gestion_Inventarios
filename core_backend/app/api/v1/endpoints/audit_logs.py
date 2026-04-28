from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_admin
from app.schemas.common import PaginatedResponse
from app.services.audit import get_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get(
    "",
    response_model=PaginatedResponse,
    summary="Listar registros de auditoría",
    description=(
        "Retorna el historial de acciones realizadas en el tenant (CREATE, UPDATE, DELETE). "
        "El audit trail es inmutable: ninguna entrada puede ser modificada o eliminada. "
        "Solo accesible para `tenant_admin` o `super_admin`."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Solo tenant_admin o super_admin"},
    },
)
async def list_audit_logs(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=100, description="Registros por página"),
    entity: str | None = Query(None, description="Filtrar por entidad (ej. products, warehouses)"),
    action: str | None = Query(None, description="Filtrar por acción: CREATE | UPDATE | DELETE"),
    user_id: str | None = Query(None, description="Filtrar por UUID del usuario que realizó la acción"),
    date_from: datetime | None = Query(None, description="Fecha de inicio (ISO 8601)"),
    date_to: datetime | None = Query(None, description="Fecha de fin (ISO 8601)"),
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_audit_logs(
        db=db,
        tenant_id=auth.tenant_id,
        page=page,
        page_size=page_size,
        entity=entity,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
    )
