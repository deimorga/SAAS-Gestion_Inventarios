from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_admin
from app.schemas.tenant import TenantConfigResponse, TenantConfigUpdate
from app.services.audit import log_action
from app.services.tenant import get_tenant_config, update_tenant_config

router = APIRouter(prefix="/tenant", tags=["Tenant"])


@router.get("/config", response_model=TenantConfigResponse)
async def get_config(
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_tenant_config(auth.tenant_id, db)


@router.patch("/config", response_model=TenantConfigResponse)
async def patch_config(
    body: TenantConfigUpdate,
    request: Request,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_auth_db),
):
    old = await get_tenant_config(auth.tenant_id, db)
    updated = await update_tenant_config(auth.tenant_id, body, db)

    changed = body.model_dump(exclude_none=True)
    if changed:
        old_vals = {k: old.config.get(k) for k in changed}
        await log_action(
            db=db,
            tenant_id=auth.tenant_id,
            entity="tenants",
            entity_id=auth.tenant_id,
            action="UPDATE",
            old_values=old_vals,
            new_values=changed,
            performed_by={"type": "user", "id": auth.user_id},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return updated
