from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, auth_activate, api_keys, tenant, audit_logs, products, categories,
    warehouses, reports, reservations, webhooks, bulk, cycle_counts,
    suppliers, channel_allocations, users,
)
from app.api.v1.endpoints.batches import router as batches_router, serials_router
from app.api.v1.endpoints.bins import router as bins_router
from app.api.v1.endpoints.inventory import ledger_router, stock_router, transactions_router

router = APIRouter(prefix="/v1")

router.include_router(auth.router)
router.include_router(auth_activate.router)
router.include_router(users.router)
router.include_router(api_keys.router)
router.include_router(tenant.router)
router.include_router(audit_logs.router)
router.include_router(products.router)
router.include_router(categories.router)
router.include_router(warehouses.router)
router.include_router(bins_router)
router.include_router(transactions_router)
router.include_router(stock_router)
router.include_router(ledger_router)
router.include_router(reports.router)
router.include_router(reservations.router)
router.include_router(webhooks.router)
router.include_router(bulk.router)
router.include_router(cycle_counts.router)
router.include_router(suppliers.router)
router.include_router(batches_router)
router.include_router(serials_router)
router.include_router(channel_allocations.router)
