from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_admin
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResponse
from app.schemas.common import PaginatedResponse
from app.services.api_key import create_api_key, list_api_keys, revoke_api_key
from app.services.audit import log_action

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("", response_model=PaginatedResponse)
async def get_api_keys(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_api_keys(db, auth.tenant_id, page, page_size, is_active)


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def add_api_key(
    body: ApiKeyCreate,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    result = await create_api_key(body, db, auth.tenant_id)
    await log_action(
        db=db,
        tenant_id=auth.tenant_id,
        entity="api_keys",
        entity_id=str(result.id),
        action="CREATE",
        new_values={"name": result.name, "scopes": [s.value for s in result.scopes]},
        performed_by={"type": "user", "id": auth.user_id},
    )
    return result


@router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    await revoke_api_key(key_id, db, auth.tenant_id)
    await log_action(
        db=db,
        tenant_id=auth.tenant_id,
        entity="api_keys",
        entity_id=key_id,
        action="DELETE",
        new_values={"is_active": False},
        performed_by={"type": "user", "id": auth.user_id},
    )
