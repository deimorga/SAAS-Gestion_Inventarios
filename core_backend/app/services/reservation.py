from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.reservation import ReservationConfirm, ReservationCreate, ReservationItemResponse, ReservationResponse

_MAX_OCC_RETRIES = 3


async def _apply_reserved_change(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    zone_id: str,
    delta_reserved: Decimal,
    delta_available: Decimal,
) -> None:
    for attempt in range(_MAX_OCC_RETRIES):
        row = (
            await db.execute(
                text(
                    "SELECT id, reserved_qty, available_qty, version "
                    "FROM stock_balances "
                    "WHERE tenant_id = :tid AND product_id = :pid AND zone_id = :zid"
                ),
                {"tid": tenant_id, "pid": product_id, "zid": zone_id},
            )
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"No hay saldo para producto {product_id} en zona {zone_id}")

        new_reserved = Decimal(str(row.reserved_qty)) + delta_reserved
        new_available = Decimal(str(row.available_qty)) + delta_available

        if new_reserved < 0:
            raise HTTPException(status_code=409, detail="reserved_qty no puede ser negativo")
        if new_available < 0:
            raise HTTPException(status_code=409, detail="Stock disponible insuficiente para la operación")

        result = await db.execute(
            text(
                "UPDATE stock_balances "
                "SET reserved_qty = :res, available_qty = :avail, version = :new_ver, updated_at = now() "
                "WHERE id = :id AND version = :old_ver"
            ),
            {"res": new_reserved, "avail": new_available, "new_ver": row.version + 1, "id": str(row.id), "old_ver": row.version},
        )
        if result.rowcount == 1:  # type: ignore[attr-defined]
            return

    raise HTTPException(status_code=409, detail="Conflicto de concurrencia al actualizar stock. Intente nuevamente.")


async def create_reservation(db: AsyncSession, tenant_id: str, body: ReservationCreate) -> ReservationResponse:
    expires_at = body.expires_at or datetime.now(timezone.utc) + timedelta(minutes=settings.RESERVATION_TTL_MINUTES)

    for item in body.items:
        row = (
            await db.execute(
                text(
                    "SELECT available_qty FROM stock_balances "
                    "WHERE tenant_id = :tid AND product_id = :pid AND zone_id = :zid"
                ),
                {"tid": tenant_id, "pid": item.product_id, "zid": item.zone_id},
            )
        ).fetchone()
        if row is None or Decimal(str(row.available_qty)) < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para producto {item.product_id} en zona {item.zone_id}",
            )

    now = datetime.now(timezone.utc)
    res_id = str(uuid4())
    await db.execute(
        text(
            "INSERT INTO reservations (id, tenant_id, reference_type, reference_id, status, expires_at, created_at, updated_at) "
            "VALUES (:id, :tid, :rt, :ri, 'ACTIVE', :exp, :now, :now)"
        ),
        {"id": res_id, "tid": tenant_id, "rt": body.reference_type, "ri": body.reference_id, "exp": expires_at, "now": now},
    )

    item_responses = []
    for item in body.items:
        item_id = str(uuid4())
        await db.execute(
            text(
                "INSERT INTO reservation_items (id, reservation_id, tenant_id, product_id, warehouse_id, zone_id, quantity, confirmed_qty) "
                "VALUES (:id, :rid, :tid, :pid, :wid, :zid, :qty, 0)"
            ),
            {"id": item_id, "rid": res_id, "tid": tenant_id, "pid": item.product_id, "wid": item.warehouse_id, "zid": item.zone_id, "qty": item.quantity},
        )
        await _apply_reserved_change(db, tenant_id, item.product_id, item.zone_id, item.quantity, -item.quantity)
        item_responses.append(
            ReservationItemResponse(
                id=item_id,
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                zone_id=item.zone_id,
                quantity=item.quantity,
                confirmed_qty=Decimal("0"),
            )
        )

    await db.commit()
    return ReservationResponse(
        id=res_id,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        status="ACTIVE",
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
        items=item_responses,
    )


async def _get_reservation_or_404(db: AsyncSession, tenant_id: str, reservation_id: str):
    row = (
        await db.execute(
            text(
                "SELECT id, tenant_id, reference_type, reference_id, status, expires_at, created_at, updated_at "
                "FROM reservations WHERE id = :id AND tenant_id = :tid"
            ),
            {"id": reservation_id, "tid": tenant_id},
        )
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return row


async def _get_items(db: AsyncSession, reservation_id: str) -> list[ReservationItemResponse]:
    rows = (
        await db.execute(
            text(
                "SELECT id, product_id, warehouse_id, zone_id, quantity, confirmed_qty "
                "FROM reservation_items WHERE reservation_id = :rid"
            ),
            {"rid": reservation_id},
        )
    ).fetchall()
    return [
        ReservationItemResponse(
            id=str(r.id),
            product_id=str(r.product_id),
            warehouse_id=str(r.warehouse_id),
            zone_id=str(r.zone_id),
            quantity=Decimal(str(r.quantity)),
            confirmed_qty=Decimal(str(r.confirmed_qty)),
        )
        for r in rows
    ]


def _to_response(row, items: list[ReservationItemResponse]) -> ReservationResponse:
    return ReservationResponse(
        id=str(row.id),
        reference_type=row.reference_type,
        reference_id=row.reference_id,
        status=row.status,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        items=items,
    )


async def get_reservation(db: AsyncSession, tenant_id: str, reservation_id: str) -> ReservationResponse:
    row = await _get_reservation_or_404(db, tenant_id, reservation_id)
    items = await _get_items(db, reservation_id)
    return _to_response(row, items)


async def list_reservations(db: AsyncSession, tenant_id: str, status: str | None) -> list[ReservationResponse]:
    extra = "AND status = :status" if status else ""
    params: dict = {"tid": tenant_id}
    if status:
        params["status"] = status

    rows = (
        await db.execute(
            text(
                f"SELECT id, tenant_id, reference_type, reference_id, status, expires_at, created_at, updated_at "
                f"FROM reservations WHERE tenant_id = :tid {extra} ORDER BY created_at DESC"
            ),
            params,
        )
    ).fetchall()

    result = []
    for row in rows:
        items = await _get_items(db, str(row.id))
        result.append(_to_response(row, items))
    return result


async def confirm_reservation(
    db: AsyncSession, tenant_id: str, reservation_id: str, body: ReservationConfirm
) -> ReservationResponse:
    row = await _get_reservation_or_404(db, tenant_id, reservation_id)
    if row.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"La reserva está en estado '{row.status}', no se puede confirmar")

    items = await _get_items(db, reservation_id)
    if not items:
        raise HTTPException(status_code=409, detail="La reserva no tiene ítems")

    total_reserved = sum(i.quantity for i in items)
    now = datetime.now(timezone.utc)

    for item in items:
        proportion = item.quantity / total_reserved
        actual_qty = (body.actual_quantity_to_issue * proportion).quantize(Decimal("0.0001"))
        surplus = item.quantity - actual_qty

        await db.execute(
            text(
                "UPDATE stock_balances "
                "SET physical_qty = physical_qty - :actual, "
                "    available_qty = available_qty + :surplus, "
                "    reserved_qty = reserved_qty - :reserved, "
                "    version = version + 1, updated_at = now() "
                "WHERE tenant_id = :tid AND product_id = :pid AND zone_id = :zid"
            ),
            {"actual": actual_qty, "surplus": surplus, "reserved": item.quantity, "tid": tenant_id, "pid": item.product_id, "zid": item.zone_id},
        )
        await db.execute(
            text(
                "INSERT INTO inventory_ledger "
                "(id, tenant_id, product_id, warehouse_id, zone_id, movement_type, qty_change, "
                "reference_type, reference_id, reason_code, created_at) "
                "VALUES (:id, :tid, :pid, :wid, :zid, 'ISSUE', :qty, 'RESERVATION_CONFIRM', :ref, 'RESERVATION', :now)"
            ),
            {
                "id": str(uuid4()), "tid": tenant_id,
                "pid": item.product_id, "wid": item.warehouse_id, "zid": item.zone_id,
                "qty": -actual_qty, "ref": body.issue_reference, "now": now,
            },
        )
        await db.execute(
            text("UPDATE reservation_items SET confirmed_qty = :cq WHERE id = :id"),
            {"cq": actual_qty, "id": item.id},
        )

    await db.execute(
        text("UPDATE reservations SET status = 'COMPLETED', updated_at = :now WHERE id = :id"),
        {"now": now, "id": reservation_id},
    )
    await db.commit()
    return await get_reservation(db, tenant_id, reservation_id)


async def cancel_reservation(db: AsyncSession, tenant_id: str, reservation_id: str) -> ReservationResponse:
    row = await _get_reservation_or_404(db, tenant_id, reservation_id)
    if row.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"La reserva está en estado '{row.status}', no se puede cancelar")

    items = await _get_items(db, reservation_id)
    for item in items:
        await _apply_reserved_change(db, tenant_id, item.product_id, item.zone_id, -item.quantity, item.quantity)

    now = datetime.now(timezone.utc)
    await db.execute(
        text("UPDATE reservations SET status = 'CANCELLED', updated_at = :now WHERE id = :id"),
        {"now": now, "id": reservation_id},
    )
    await db.commit()
    return await get_reservation(db, tenant_id, reservation_id)
