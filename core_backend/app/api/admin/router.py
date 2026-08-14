from fastapi import APIRouter

from app.api.admin.endpoints import (
    admin_auth,
    admin_products,
    admin_stock,
    admin_tenants,
    admin_users,
)

router = APIRouter(prefix="/admin")
router.include_router(admin_auth.router)
router.include_router(admin_tenants.router)
router.include_router(admin_products.router)
router.include_router(admin_stock.router)
router.include_router(admin_users.router)
