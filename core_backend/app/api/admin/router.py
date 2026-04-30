from fastapi import APIRouter

from app.api.admin.endpoints import admin_auth, admin_tenants

router = APIRouter(prefix="/admin")
router.include_router(admin_auth.router)
router.include_router(admin_tenants.router)
