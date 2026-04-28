from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cycle_count import (
    CycleCountClose,
    CycleCountCreate,
    CycleCountItemResponse,
    CycleCountItemUpdate,
    CycleCountSessionResponse,
)


async def _get_session_or_404(db: AsyncSession, tenant_id: str, session_id: str):
    row = (
        await db.execute(
            text(
                "SELECT id, tenant_id, warehouse_id, label, status, apply_adjustments, created_at, closed_at "
                "FROM cycle_count_sessions WHERE id = :id AND tenant_id = :tid"
            ),
            {"id": session_id, "tid": tenant_id},
        )
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Sesión de conteo no encontrada")
    return row


async def _get_items(db: AsyncSession, session_id: str) -> list[CycleCountItemResponse]:
    rows = (
        await db.execute(
            text(
                "SELECT id, product_id, zone_id, expected_qty, counted_qty "
                "FROM cycle_count_items WHERE session_id = :sid ORDER BY created_at"
            ),
            {"sid": session_id},
        )
    ).fetchall()
    return [
        CycleCountItemResponse(
            id=str(r.id),
            product_id=str(r.product_id),
            zone_id=str(r.zone_id),
            expected_qty=Decimal(str(r.expected_qty)),
            counted_qty=Decimal(str(r.counted_qty)) if r.counted_qty is not None else None,
            variance=(
                Decimal(str(r.counted_qty)) - Decimal(str(r.expected_qty))
                if r.counted_qty is not None
                else None
            ),
        )
        for r in rows
    ]


def _to_session_response(row, items: list[CycleCountItemResponse]) -> CycleCountSessionResponse:
    return CycleCountSessionResponse(
        id=str(row.id),
        warehouse_id=str(row.warehouse_id),
        label=row.label,
        status=row.status,
        apply_adjustments=bool(row.apply_adjustments),
        created_at=row.created_at,
        closed_at=row.closed_at,
        items=items,
    )


async def create_session(db: AsyncSession, tenant_id: str, body: CycleCountCreate) -> CycleCountSessionResponse:
    wh = (
        await db.execute(
            text("SELECT id FROM warehouses WHERE id = :id AND tenant_id = :tid AND is_active = true"),
            {"id": body.warehouse_id, "tid": tenant_id},
        )
    ).fetchone()
    if wh is None:
        raise HTTPException(status_code=404, detail="Almacén no encontrado o inactivo")

    sid = str(uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO cycle_count_sessions (id, tenant_id, warehouse_id, label, status, apply_adjustments, created_at) "
            "VALUES (:id, :tid, :wid, :label, 'OPEN', :apply, :now)"
        ),
        {"id": sid, "tid": tenant_id, "wid": body.warehouse_id, "label": body.label, "apply": body.apply_adjustments, "now": now},
    )

    balance_rows = (
        await db.execute(
            text(
                "SELECT product_id, zone_id, physical_qty FROM stock_balances "
                "WHERE tenant_id = :tid AND warehouse_id = :wid"
            ),
            {"tid": tenant_id, "wid": body.warehouse_id},
        )
    ).fetchall()

    for b in balance_rows:
        await db.execute(
            text(
                "INSERT INTO cycle_count_items (id, session_id, tenant_id, product_id, zone_id, expected_qty, created_at, updated_at) "
                "VALUES (:id, :sid, :tid, :pid, :zid, :exp, :now, :now)"
            ),
            {
                "id": str(uuid4()),
                "sid": sid,
                "tid": tenant_id,
                "pid": str(b.product_id),
                "zid": str(b.zone_id),
                "exp": b.physical_qty,
                "now": now,
            },
        )

    await db.commit()
    row = await _get_session_or_404(db, tenant_id, sid)
    items = await _get_items(db, sid)
    return _to_session_response(row, items)


async def list_sessions(
    db: AsyncSession, tenant_id: str, status: str | None
) -> list[CycleCountSessionResponse]:
    extra = "AND status = :status" if status else ""
    params: dict = {"tid": tenant_id}
    if status:
        params["status"] = status

    rows = (
        await db.execute(
            text(
                f"SELECT id, tenant_id, warehouse_id, label, status, apply_adjustments, created_at, closed_at "
                f"FROM cycle_count_sessions WHERE tenant_id = :tid {extra} ORDER BY created_at DESC"
            ),
            params,
        )
    ).fetchall()

    result = []
    for row in rows:
        items = await _get_items(db, str(row.id))
        result.append(_to_session_response(row, items))
    return result


async def get_session(db: AsyncSession, tenant_id: str, session_id: str) -> CycleCountSessionResponse:
    row = await _get_session_or_404(db, tenant_id, session_id)
    items = await _get_items(db, session_id)
    return _to_session_response(row, items)


async def record_count(
    db: AsyncSession, tenant_id: str, session_id: str, item_id: str, body: CycleCountItemUpdate
) -> CycleCountItemResponse:
    session_row = await _get_session_or_404(db, tenant_id, session_id)
    if session_row.status != "OPEN":
        raise HTTPException(status_code=409, detail="La sesión no está abierta")

    item_row = (
        await db.execute(
            text(
                "SELECT id, product_id, zone_id, expected_qty, counted_qty "
                "FROM cycle_count_items WHERE id = :id AND session_id = :sid"
            ),
            {"id": item_id, "sid": session_id},
        )
    ).fetchone()
    if item_row is None:
        raise HTTPException(status_code=404, detail="Ítem de conteo no encontrado")

    await db.execute(
        text("UPDATE cycle_count_items SET counted_qty = :qty, updated_at = now() WHERE id = :id"),
        {"qty": body.counted_qty, "id": item_id},
    )
    await db.commit()

    expected = Decimal(str(item_row.expected_qty))
    return CycleCountItemResponse(
        id=str(item_row.id),
        product_id=str(item_row.product_id),
        zone_id=str(item_row.zone_id),
        expected_qty=expected,
        counted_qty=body.counted_qty,
        variance=body.counted_qty - expected,
    )


async def close_session(
    db: AsyncSession, tenant_id: str, session_id: str, body: CycleCountClose
) -> CycleCountSessionResponse:
    session_row = await _get_session_or_404(db, tenant_id, session_id)
    if session_row.status != "OPEN":
        raise HTTPException(status_code=409, detail="La sesión ya está cerrada")

    items = await _get_items(db, session_id)
    now = datetime.now(timezone.utc)
    warehouse_id = str(session_row.warehouse_id)

    if bool(session_row.apply_adjustments):
        for item in items:
            if item.counted_qty is None or item.variance == Decimal("0"):
                continue

            tx_id = str(uuid4())
            await db.execute(
                text(
                    "INSERT INTO transactions (id, tenant_id, transaction_type, reference_type, reference_id, "
                    "reason_code, status, items_processed, created_at) "
                    "VALUES (:id, :tid, 'ADJUSTMENT', 'CYCLE_COUNT', :ref, 'CONTEO_FISICO', 'COMPLETED', 1, :now)"
                ),
                {"id": tx_id, "tid": tenant_id, "ref": body.reference_id, "now": now},
            )

            await db.execute(
                text(
                    "UPDATE stock_balances "
                    "SET physical_qty = :new_qty, "
                    "    available_qty = :new_qty - reserved_qty, "
                    "    version = version + 1, "
                    "    updated_at = now() "
                    "WHERE tenant_id = :tid AND product_id = :pid AND zone_id = :zid"
                ),
                {"new_qty": item.counted_qty, "tid": tenant_id, "pid": item.product_id, "zid": item.zone_id},
            )

            await db.execute(
                text(
                    "INSERT INTO inventory_ledger "
                    "(id, tenant_id, product_id, warehouse_id, zone_id, movement_type, qty_change, "
                    "reference_type, reference_id, reason_code, created_at) "
                    "VALUES (:id, :tid, :pid, :wid, :zid, 'ADJUSTMENT', :qty, 'CYCLE_COUNT', :ref, 'CONTEO_FISICO', :now)"
                ),
                {
                    "id": str(uuid4()),
                    "tid": tenant_id,
                    "pid": item.product_id,
                    "wid": warehouse_id,
                    "zid": item.zone_id,
                    "qty": item.variance,
                    "ref": body.reference_id,
                    "now": now,
                },
            )

    await db.execute(
        text("UPDATE cycle_count_sessions SET status = 'CLOSED', closed_at = :now WHERE id = :id"),
        {"now": now, "id": session_id},
    )
    await db.commit()

    row = await _get_session_or_404(db, tenant_id, session_id)
    updated_items = await _get_items(db, session_id)
    return _to_session_response(row, updated_items)
