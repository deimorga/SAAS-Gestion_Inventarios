from fastapi import APIRouter

from app.api.v1.endpoints import auth, api_keys, tenant, audit_logs, products, categories, warehouses
from app.api.v1.endpoints.inventory import ledger_router, stock_router, transactions_router

router = APIRouter(prefix="/v1")

router.include_router(auth.router)
router.include_router(api_keys.router)
router.include_router(tenant.router)
router.include_router(audit_logs.router)
router.include_router(products.router)
router.include_router(categories.router)
router.include_router(warehouses.router)
router.include_router(transactions_router)
router.include_router(stock_router)
router.include_router(ledger_router)
