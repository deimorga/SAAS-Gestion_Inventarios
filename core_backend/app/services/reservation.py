"""Reservas de stock con desglose real por lote y ubicación.

Cada ítem de reserva se reparte en asignaciones (`reservation_allocations`), una
por saldo concreto (producto + zona + bin + lote + proveedor) del que se apartó stock.

- Sin lote pedido y con `track_lots`, el inventario elige: primero el lote que vence
  antes (FEFO) y, sin vencimientos, el que entró primero (FIFO). Si un lote no
  alcanza, sigue con el siguiente.
- Las filas de saldo se bloquean (`FOR UPDATE`) mientras se reparte, así dos reservas
  simultáneas no pueden apartar las mismas unidades.
- La confirmación saca de cada asignación en el orden en que se eligió, deja en el
  ledger un ISSUE por lote/bin con la orden del cliente como `reference_id` y libera
  lo que no se despachó.

Las reservas creadas antes de la migración 015 no tienen asignaciones: se confirman,
cancelan y expiran contra el saldo único de producto + zona, como antes.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.reservation import Reservation, ReservationAllocation, ReservationItem
from app.models.transaction import Transaction
from app.schemas.reservation import (
    ReservationAllocationResponse,
    ReservationConfirm,
    ReservationCreate,
    ReservationItemResponse,
    ReservationResponse,
)
from app.services.traceability import get_bin_in_zone, get_supplier_of_tenant, opt_str

_QTY = Decimal("0.0001")

# Vencimiento y fecha de primera entrada de un lote. Salen del registro del lote
# (batches) y, para lotes anteriores a que las entradas crearan lotes, del ledger.
_LOT_EXPIRY = (
    "COALESCE(bt.expiry_date, (SELECT min(l.expiry_date) FROM inventory_ledger l "
    " WHERE l.tenant_id = sb.tenant_id AND l.product_id = sb.product_id AND l.lot_number = sb.lot_number))"
)
_LOT_FIRST_IN = (
    "COALESCE(bt.created_at, (SELECT min(l.created_at) FROM inventory_ledger l "
    " WHERE l.tenant_id = sb.tenant_id AND l.product_id = sb.product_id AND l.lot_number = sb.lot_number "
    " AND l.qty_change > 0))"
)

# Con track_lots: FEFO → FIFO; el stock sin lote (histórico) queda al final.
_ORDER_TRACK_LOTS = (
    "(sb.lot_number IS NULL), expiry ASC NULLS LAST, first_in ASC NULLS LAST, sb.lot_number, "
    "(sb.bin_id IS NOT NULL), bin_code NULLS FIRST, sb.id"
)
# Sin track_lots: primero el stock sin lote y sin ubicar (como siempre), luego por bin.
_ORDER_PLAIN = (
    "(sb.lot_number IS NOT NULL), (sb.bin_id IS NOT NULL), bin_code NULLS FIRST, "
    "first_in ASC NULLS LAST, sb.id"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_product_row(db: AsyncSession, tenant_id: str, product_id: str):
    return (
        await db.execute(
            text("SELECT id, sku, track_lots, current_cpp FROM products WHERE id = :pid AND tenant_id = :tid"),
            {"pid": product_id, "tid": tenant_id},
        )
    ).fetchone()


async def _candidate_balances(db: AsyncSession, tenant_id: str, item, track_lots: bool):
    """Saldos con stock disponible para el ítem, en orden de consumo y bloqueados."""
    filters = ""
    params: dict = {"tid": tenant_id, "pid": item.product_id, "zid": item.zone_id}
    if item.lot_number:
        filters += " AND sb.lot_number = :lot"
        params["lot"] = item.lot_number
    if item.bin_id:
        filters += " AND sb.bin_id = :bin"
        params["bin"] = str(item.bin_id)
    if item.supplier_id:
        filters += " AND sb.supplier_id = :sup"
        params["sup"] = str(item.supplier_id)

    order = _ORDER_TRACK_LOTS if track_lots else _ORDER_PLAIN
    return (
        await db.execute(
            text(
                "SELECT sb.id, sb.lot_number, sb.bin_id, sb.supplier_id, sb.available_qty, "
                f"       b.code AS bin_code, {_LOT_EXPIRY} AS expiry, {_LOT_FIRST_IN} AS first_in "
                "FROM stock_balances sb "
                "LEFT JOIN bins b ON b.id = sb.bin_id "
                "LEFT JOIN batches bt ON bt.tenant_id = sb.tenant_id AND bt.product_id = sb.product_id "
                "     AND bt.batch_number = sb.lot_number AND bt.supplier_id IS NOT DISTINCT FROM sb.supplier_id "
                "WHERE sb.tenant_id = :tid AND sb.product_id = :pid AND sb.zone_id = :zid "
                f"  AND sb.available_qty > 0 {filters} "
                f"ORDER BY {order} "
                "FOR UPDATE OF sb"
            ),
            params,
        )
    ).fetchall()


async def _lock_balance(db: AsyncSession, tenant_id: str, balance_id: str):
    return (
        await db.execute(
            text(
                "SELECT id, warehouse_id, zone_id, physical_qty, reserved_qty, available_qty "
                "FROM stock_balances WHERE id = :id AND tenant_id = :tid FOR UPDATE"
            ),
            {"id": balance_id, "tid": tenant_id},
        )
    ).fetchone()


async def _set_balance(db: AsyncSession, balance_id: str, physical, reserved, available) -> None:
    await db.execute(
        text(
            "UPDATE stock_balances "
            "SET physical_qty = :phys, reserved_qty = :res, available_qty = :avail, "
            "    version = version + 1, updated_at = now() "
            "WHERE id = :id"
        ),
        {"phys": physical, "res": reserved, "avail": available, "id": balance_id},
    )


async def _item_allocations(db: AsyncSession, tenant_id: str, item_row) -> list[dict]:
    """Asignaciones del ítem en orden de consumo. Reservas anteriores a la 015 no tienen:
    se usa el saldo de producto + zona, como hacía la versión anterior."""
    rows = (
        await db.execute(
            text(
                "SELECT id, stock_balance_id, lot_number, bin_id, supplier_id, quantity "
                "FROM reservation_allocations WHERE reservation_item_id = :iid ORDER BY seq"
            ),
            {"iid": str(item_row.id)},
        )
    ).fetchall()
    if rows:
        return [
            {
                "id": str(r.id), "balance_id": str(r.stock_balance_id), "lot_number": r.lot_number,
                "bin_id": opt_str(r.bin_id), "supplier_id": opt_str(r.supplier_id),
                "quantity": Decimal(str(r.quantity)),
            }
            for r in rows
        ]

    legacy = (
        await db.execute(
            text(
                "SELECT id, lot_number, bin_id, supplier_id FROM stock_balances "
                "WHERE tenant_id = :tid AND product_id = :pid AND zone_id = :zid "
                "ORDER BY (bin_id IS NOT NULL), (lot_number IS NOT NULL), reserved_qty DESC LIMIT 1"
            ),
            {"tid": tenant_id, "pid": str(item_row.product_id), "zid": str(item_row.zone_id)},
        )
    ).fetchone()
    if legacy is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay saldo para producto {item_row.product_id} en zona {item_row.zone_id}",
        )
    return [{
        "id": None, "balance_id": str(legacy.id), "lot_number": legacy.lot_number,
        "bin_id": opt_str(legacy.bin_id), "supplier_id": opt_str(legacy.supplier_id),
        "quantity": Decimal(str(item_row.quantity)),
    }]


async def _item_rows(db: AsyncSession, reservation_id: str):
    return (
        await db.execute(
            text(
                "SELECT id, product_id, warehouse_id, zone_id, quantity, confirmed_qty, "
                "       lot_number, bin_id, supplier_id "
                "FROM reservation_items WHERE reservation_id = :rid"
            ),
            {"rid": reservation_id},
        )
    ).fetchall()


async def _release(db: AsyncSession, tenant_id: str, reservation_id: str) -> None:
    """Devuelve a disponible todo lo apartado por una reserva ACTIVE (cancelar / expirar)."""
    for item_row in await _item_rows(db, reservation_id):
        for alloc in await _item_allocations(db, tenant_id, item_row):
            bal = await _lock_balance(db, tenant_id, alloc["balance_id"])
            if bal is None:
                raise HTTPException(status_code=404, detail="Saldo de la reserva no encontrado")
            reserved = Decimal(str(bal.reserved_qty)) - alloc["quantity"]
            if reserved < 0:
                raise HTTPException(status_code=409, detail="reserved_qty no puede ser negativo")
            await _set_balance(
                db, alloc["balance_id"], bal.physical_qty, reserved,
                Decimal(str(bal.available_qty)) + alloc["quantity"],
            )


# ── Crear ─────────────────────────────────────────────────────────────────────

async def create_reservation(db: AsyncSession, tenant_id: str, body: ReservationCreate) -> ReservationResponse:
    expires_at = body.expires_at or datetime.now(timezone.utc) + timedelta(minutes=settings.RESERVATION_TTL_MINUTES)

    # Repartir todos los ítems antes de escribir. `claimed` acumula lo apartado por
    # esta misma reserva, por si dos ítems piden el mismo producto en la misma zona.
    claimed: dict[str, Decimal] = {}
    plans = []
    for item in body.items:
        product = await _get_product_row(db, tenant_id, item.product_id)
        await get_bin_in_zone(db, item.bin_id, item.zone_id, tenant_id)
        await get_supplier_of_tenant(db, item.supplier_id, tenant_id)

        allocations = []
        remaining = item.quantity
        if product is not None:
            for c in await _candidate_balances(db, tenant_id, item, bool(product.track_lots)):
                available = Decimal(str(c.available_qty)) - claimed.get(str(c.id), Decimal("0"))
                if available <= 0:
                    continue
                take = min(available, remaining)
                allocations.append({
                    "balance_id": str(c.id), "lot_number": c.lot_number,
                    "bin_id": opt_str(c.bin_id), "supplier_id": opt_str(c.supplier_id), "quantity": take,
                })
                claimed[str(c.id)] = claimed.get(str(c.id), Decimal("0")) + take
                remaining -= take
                if remaining <= 0:
                    break

        if remaining > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para producto {item.product_id} en zona {item.zone_id}",
            )
        plans.append((item, allocations))

    now = datetime.now(timezone.utc)
    res_id = str(uuid4())
    db.add(Reservation(
        id=res_id, tenant_id=tenant_id, reference_type=body.reference_type, reference_id=body.reference_id,
        status="ACTIVE", expires_at=expires_at, created_at=now, updated_at=now,
    ))
    await db.flush()

    allocation_rows = []
    for item, allocations in plans:
        item_id = str(uuid4())
        db.add(ReservationItem(
            id=item_id, reservation_id=res_id, tenant_id=tenant_id,
            product_id=item.product_id, warehouse_id=item.warehouse_id, zone_id=item.zone_id,
            quantity=item.quantity, confirmed_qty=Decimal("0"),
            lot_number=item.lot_number, bin_id=opt_str(item.bin_id), supplier_id=opt_str(item.supplier_id),
        ))
        for seq, a in enumerate(allocations):
            allocation_rows.append(ReservationAllocation(
                id=str(uuid4()), tenant_id=tenant_id, reservation_item_id=item_id,
                stock_balance_id=a["balance_id"], seq=seq,
                lot_number=a["lot_number"], bin_id=a["bin_id"], supplier_id=a["supplier_id"],
                quantity=a["quantity"], confirmed_qty=Decimal("0"), created_at=now,
            ))
    await db.flush()
    db.add_all(allocation_rows)
    await db.flush()

    # Las filas ya están bloqueadas por _candidate_balances: se actualizan sin carrera.
    for balance_id, qty in claimed.items():
        await db.execute(
            text(
                "UPDATE stock_balances "
                "SET reserved_qty = reserved_qty + :q, available_qty = available_qty - :q, "
                "    version = version + 1, updated_at = now() "
                "WHERE id = :id"
            ),
            {"q": qty, "id": balance_id},
        )

    await db.commit()
    return await get_reservation(db, tenant_id, res_id)


# ── Leer ──────────────────────────────────────────────────────────────────────

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
    alloc_rows = (
        await db.execute(
            text(
                "SELECT ra.reservation_item_id, ra.lot_number, ra.bin_id, b.code AS bin_code, b.name AS bin_name, "
                "       ra.supplier_id, ra.quantity, ra.confirmed_qty, "
                "       COALESCE(bt.expiry_date, (SELECT min(l.expiry_date) FROM inventory_ledger l "
                "                 WHERE l.tenant_id = ra.tenant_id AND l.product_id = ri.product_id "
                "                   AND l.lot_number = ra.lot_number)) AS expiry_date "
                "FROM reservation_allocations ra "
                "JOIN reservation_items ri ON ri.id = ra.reservation_item_id "
                "LEFT JOIN bins b ON b.id = ra.bin_id "
                "LEFT JOIN batches bt ON bt.tenant_id = ra.tenant_id AND bt.product_id = ri.product_id "
                "     AND bt.batch_number = ra.lot_number AND bt.supplier_id IS NOT DISTINCT FROM ra.supplier_id "
                "WHERE ri.reservation_id = :rid "
                "ORDER BY ra.reservation_item_id, ra.seq"
            ),
            {"rid": reservation_id},
        )
    ).fetchall()
    by_item: dict[str, list[ReservationAllocationResponse]] = {}
    for a in alloc_rows:
        by_item.setdefault(str(a.reservation_item_id), []).append(
            ReservationAllocationResponse(
                lot_number=a.lot_number, bin_id=opt_str(a.bin_id), bin_code=a.bin_code, bin_name=a.bin_name,
                supplier_id=opt_str(a.supplier_id), expiry_date=a.expiry_date,
                quantity=Decimal(str(a.quantity)), confirmed_qty=Decimal(str(a.confirmed_qty)),
            )
        )

    return [
        ReservationItemResponse(
            id=str(r.id),
            product_id=str(r.product_id),
            warehouse_id=str(r.warehouse_id),
            zone_id=str(r.zone_id),
            quantity=Decimal(str(r.quantity)),
            confirmed_qty=Decimal(str(r.confirmed_qty)),
            lot_number=r.lot_number,
            bin_id=opt_str(r.bin_id),
            supplier_id=opt_str(r.supplier_id),
            allocations=by_item.get(str(r.id), []),
        )
        for r in await _item_rows(db, reservation_id)
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


# ── Confirmar ─────────────────────────────────────────────────────────────────

async def confirm_reservation(
    db: AsyncSession, tenant_id: str, reservation_id: str, body: ReservationConfirm
) -> ReservationResponse:
    row = await _get_reservation_or_404(db, tenant_id, reservation_id)
    if row.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"La reserva está en estado '{row.status}', no se puede confirmar")

    items = await _item_rows(db, reservation_id)
    if not items:
        raise HTTPException(status_code=409, detail="La reserva no tiene ítems")

    total_reserved = sum(Decimal(str(i.quantity)) for i in items)
    total_to_issue = body.actual_quantity_to_issue
    if total_to_issue > total_reserved:
        raise HTTPException(
            status_code=422,
            detail=f"No se puede despachar más de lo reservado: reservado {total_reserved}, solicitado {total_to_issue}",
        )

    now = datetime.now(timezone.utc)
    # La salida es una transacción propia: el ledger ya no queda con transaction_id nulo.
    tx_id = str(uuid4())
    db.add(Transaction(
        id=tx_id, tenant_id=tenant_id, transaction_type="ISSUE",
        reference_type="RESERVATION_CONFIRM", reference_id=body.issue_reference,
        reason_code="RESERVATION", status="COMPLETED", items_processed=len(items),
        notes=f"Reserva {reservation_id} ({row.reference_type} {row.reference_id})",
        created_at=now,
    ))
    await db.flush()

    # La cantidad a despachar se reparte entre los ítems en proporción a lo reservado
    # (comportamiento previo). El último ítem absorbe el redondeo para que el total cuadre.
    issued_so_far = Decimal("0")
    for idx, item in enumerate(items):
        item_qty = Decimal(str(item.quantity))
        if idx == len(items) - 1:
            actual_qty = total_to_issue - issued_so_far
        else:
            actual_qty = (total_to_issue * item_qty / total_reserved).quantize(_QTY)
        actual_qty = max(Decimal("0"), min(actual_qty, item_qty))
        issued_so_far += actual_qty

        product = await _get_product_row(db, tenant_id, str(item.product_id))
        unit_cost = product.current_cpp if product is not None else None

        # Se despacha en el orden en que se apartó (FEFO/FIFO); lo que sobra se libera.
        left = actual_qty
        for alloc in await _item_allocations(db, tenant_id, item):
            take = min(left, alloc["quantity"])
            left -= take

            bal = await _lock_balance(db, tenant_id, alloc["balance_id"])
            if bal is None:
                raise HTTPException(status_code=404, detail="Saldo de la reserva no encontrado")
            physical = Decimal(str(bal.physical_qty)) - take
            reserved = Decimal(str(bal.reserved_qty)) - alloc["quantity"]
            available = Decimal(str(bal.available_qty)) + (alloc["quantity"] - take)
            if physical < 0 or reserved < 0:
                raise HTTPException(status_code=409, detail="Stock inconsistente para confirmar la reserva")
            await _set_balance(db, alloc["balance_id"], physical, reserved, available)

            if take > 0:
                # reference_id = la orden del cliente (la de la reserva): así se responde
                # "¿en qué órdenes se usó el lote X?" filtrando el ledger por lote.
                await db.execute(
                    text(
                        "INSERT INTO inventory_ledger "
                        "(id, tenant_id, transaction_id, product_id, warehouse_id, zone_id, bin_id, supplier_id, "
                        " movement_type, qty_change, unit_cost, lot_number, "
                        " reference_type, reference_id, reason_code, created_at) "
                        "VALUES (:id, :tid, :txid, :pid, :wid, :zid, :bin, :sup, 'ISSUE', :qty, :cost, :lot, "
                        "        'RESERVATION_CONFIRM', :ref, 'RESERVATION', :now)"
                    ),
                    {
                        "id": str(uuid4()), "tid": tenant_id, "txid": tx_id,
                        "pid": str(item.product_id), "wid": str(bal.warehouse_id), "zid": str(bal.zone_id),
                        "bin": alloc["bin_id"], "sup": alloc["supplier_id"],
                        "qty": -take, "cost": unit_cost, "lot": alloc["lot_number"],
                        "ref": row.reference_id, "now": now,
                    },
                )
            if alloc["id"] is not None:
                await db.execute(
                    text("UPDATE reservation_allocations SET confirmed_qty = :cq WHERE id = :id"),
                    {"cq": take, "id": alloc["id"]},
                )

        await db.execute(
            text("UPDATE reservation_items SET confirmed_qty = :cq WHERE id = :id"),
            {"cq": actual_qty, "id": str(item.id)},
        )

    await db.execute(
        text("UPDATE reservations SET status = 'COMPLETED', updated_at = :now WHERE id = :id"),
        {"now": now, "id": reservation_id},
    )
    await db.commit()
    return await get_reservation(db, tenant_id, reservation_id)


# ── Cancelar / expirar ────────────────────────────────────────────────────────

async def cancel_reservation(db: AsyncSession, tenant_id: str, reservation_id: str) -> ReservationResponse:
    row = await _get_reservation_or_404(db, tenant_id, reservation_id)
    if row.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"La reserva está en estado '{row.status}', no se puede cancelar")

    await _release(db, tenant_id, reservation_id)

    now = datetime.now(timezone.utc)
    await db.execute(
        text("UPDATE reservations SET status = 'CANCELLED', updated_at = :now WHERE id = :id"),
        {"now": now, "id": reservation_id},
    )
    await db.commit()
    return await get_reservation(db, tenant_id, reservation_id)


async def expire_reservation(db: AsyncSession, tenant_id: str, reservation_id: str) -> None:
    """Libera una reserva vencida. No hace commit: lo hace el bucle de expiración."""
    await _release(db, tenant_id, reservation_id)
    await db.execute(
        text("UPDATE reservations SET status = 'EXPIRED', updated_at = now() WHERE id = :id"),
        {"id": reservation_id},
    )
