from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_db, require_catalog_read, require_catalog_write
from app.schemas.catalog import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.audit import log_action
from app.services.category import create_category, delete_category, get_category, list_categories, update_category

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list)
async def get_categories(
    flat: bool = Query(False),
    include_counts: bool = Query(False),
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await list_categories(db, auth.tenant_id, flat, include_counts)


@router.post("", response_model=CategoryResponse, status_code=201)
async def add_category(
    body: CategoryCreate,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    cat = await create_category(body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="categories", entity_id=str(cat.id),
        action="CREATE", new_values={"name": cat.name, "path": cat.path},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return cat


@router.get("/{cat_id}", response_model=CategoryResponse)
async def get_category_detail(
    cat_id: str,
    auth: AuthContext = Depends(require_catalog_read),
    db: AsyncSession = Depends(get_auth_db),
):
    return await get_category(cat_id, db, auth.tenant_id)


@router.patch("/{cat_id}", response_model=CategoryResponse)
async def patch_category(
    cat_id: str,
    body: CategoryUpdate,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    updated = await update_category(cat_id, body, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="categories", entity_id=cat_id,
        action="UPDATE", new_values=body.model_dump(exclude_none=True),
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{cat_id}", status_code=204)
async def remove_category(
    cat_id: str,
    request: Request,
    auth: AuthContext = Depends(require_catalog_write),
    db: AsyncSession = Depends(get_auth_db),
):
    await delete_category(cat_id, db, auth.tenant_id)
    await log_action(
        db=db, tenant_id=auth.tenant_id, entity="categories", entity_id=cat_id,
        action="DELETE", new_values={"is_active": False},
        performed_by={"type": "user", "id": auth.user_id},
        ip_address=request.client.host if request.client else None,
    )
