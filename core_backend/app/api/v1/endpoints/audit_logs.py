from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_admin
from app.schemas.common import PaginatedResponse
from app.services.audit import get_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=PaginatedResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    entity: str | None = Query(None),
    action: str | None = Query(None),
    user_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
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
