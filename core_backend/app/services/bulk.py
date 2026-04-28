from fastapi import HTTPException
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.schemas.bulk import BulkIssueRequest, BulkReceiptRequest, BulkResult, BulkTransferRequest
from app.schemas.bulk import BulkItemResult
from app.services.inventory import process_issue, process_receipt, process_transfer


async def _run_in_session(tenant_id: str, fn, body, created_by: str) -> str:
    """Ejecuta fn(body, session, tenant_id, created_by) en sesión independiente. Retorna transaction_id."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": tenant_id},
        )
        tx = await fn(body, session, tenant_id, created_by)
        return str(tx.transaction_id)


async def bulk_receipts(tenant_id: str, request: BulkReceiptRequest, created_by: str) -> BulkResult:
    results: list[BulkItemResult] = []
    for i, item in enumerate(request.items):
        try:
            tx_id = await _run_in_session(tenant_id, process_receipt, item, created_by)
            results.append(BulkItemResult(index=i, status="ok", transaction_id=tx_id))
        except HTTPException as exc:
            results.append(BulkItemResult(index=i, status="error", detail=exc.detail))
        except Exception:
            results.append(BulkItemResult(index=i, status="error", detail="Error interno al procesar ítem"))

    succeeded = sum(1 for r in results if r.status == "ok")
    return BulkResult(
        total=len(request.items),
        succeeded=succeeded,
        failed=len(request.items) - succeeded,
        results=results,
    )


async def bulk_issues(tenant_id: str, request: BulkIssueRequest, created_by: str) -> BulkResult:
    results: list[BulkItemResult] = []
    for i, item in enumerate(request.items):
        try:
            tx_id = await _run_in_session(tenant_id, process_issue, item, created_by)
            results.append(BulkItemResult(index=i, status="ok", transaction_id=tx_id))
        except HTTPException as exc:
            results.append(BulkItemResult(index=i, status="error", detail=exc.detail))
        except Exception:
            results.append(BulkItemResult(index=i, status="error", detail="Error interno al procesar ítem"))

    succeeded = sum(1 for r in results if r.status == "ok")
    return BulkResult(
        total=len(request.items),
        succeeded=succeeded,
        failed=len(request.items) - succeeded,
        results=results,
    )


async def bulk_transfers(tenant_id: str, request: BulkTransferRequest, created_by: str) -> BulkResult:
    results: list[BulkItemResult] = []
    for i, item in enumerate(request.items):
        try:
            tx_id = await _run_in_session(tenant_id, process_transfer, item, created_by)
            results.append(BulkItemResult(index=i, status="ok", transaction_id=tx_id))
        except HTTPException as exc:
            results.append(BulkItemResult(index=i, status="error", detail=exc.detail))
        except Exception:
            results.append(BulkItemResult(index=i, status="error", detail="Error interno al procesar ítem"))

    succeeded = sum(1 for r in results if r.status == "ok")
    return BulkResult(
        total=len(request.items),
        succeeded=succeeded,
        failed=len(request.items) - succeeded,
        results=results,
    )
