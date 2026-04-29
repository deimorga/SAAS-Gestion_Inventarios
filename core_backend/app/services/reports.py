from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reports import (
    ExpiringBatch,
    ExpiringBatchesResponse,
    KardexMovement,
    KardexProductSummary,
    KardexResponse,
    LowStockItem,
    LowStockResponse,
    SnapshotCreate,
    SnapshotResponse,
    ValuationDetail,
    ValuationResponse,
)


async def get_kardex(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    warehouse_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> KardexResponse:
    prod_row = (
        await db.execute(
            text("SELECT id, sku, name, current_cpp FROM products WHERE id = :pid AND tenant_id = :tid"),
            {"pid": product_id, "tid": tenant_id},
        )
    ).fetchone()
    if prod_row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    filters = ["l.tenant_id = :tid", "l.product_id = :pid"]
    params: dict = {"tid": tenant_id, "pid": product_id}

    if warehouse_id:
        filters.append("l.warehouse_id = :wid")
        params["wid"] = warehouse_id
    if date_from:
        filters.append("l.created_at >= :dfrom")
        params["dfrom"] = date_from
    if date_to:
        filters.append("l.created_at <= :dto")
        params["dto"] = date_to

    where = " AND ".join(filters)

    count_row = (await db.execute(text(f"SELECT COUNT(*) FROM inventory_ledger l WHERE {where}"), params)).scalar()
    total = int(count_row or 0)

    initial_balance = Decimal("0")
    if date_from:
        ib_params = {"tid": tenant_id, "pid": product_id, "dfrom": date_from}
        ib_where = "l.tenant_id = :tid AND l.product_id = :pid AND l.created_at < :dfrom"
        if warehouse_id:
            ib_where += " AND l.warehouse_id = :wid"
            ib_params["wid"] = warehouse_id
        ib_row = (await db.execute(text(f"SELECT COALESCE(SUM(l.qty_change), 0) FROM inventory_ledger l WHERE {ib_where}"), ib_params)).scalar()
        initial_balance = Decimal(str(ib_row or 0))

    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            text(
                f"SELECT l.id, l.created_at, l.movement_type, l.reason_code, l.reference_type, "
                f"l.reference_id, l.qty_change, l.unit_cost, l.warehouse_id, l.zone_id "
                f"FROM inventory_ledger l WHERE {where} "
                f"ORDER BY l.created_at ASC "
                f"LIMIT :lim OFFSET :off"
            ),
            {**params, "lim": page_size, "off": offset},
        )
    ).fetchall()

    movements: list[KardexMovement] = []
    running = initial_balance
    for r in rows:
        change = Decimal(str(r.qty_change))
        running += change
        movements.append(
            KardexMovement(
                id=str(r.id),
                date=r.created_at,
                movement_type=r.movement_type,
                reason_code=r.reason_code,
                reference_type=r.reference_type,
                reference_id=r.reference_id,
                qty_in=change if change > 0 else Decimal("0"),
                qty_out=abs(change) if change < 0 else Decimal("0"),
                unit_cost=Decimal(str(r.unit_cost)) if r.unit_cost is not None else None,
                balance_after=running,
                warehouse_id=str(r.warehouse_id),
                zone_id=str(r.zone_id),
            )
        )

    return KardexResponse(
        product=KardexProductSummary(
            id=str(prod_row.id),
            sku=prod_row.sku,
            name=prod_row.name,
            current_cpp=Decimal(str(prod_row.current_cpp)),
        ),
        initial_balance=initial_balance,
        final_balance=running,
        movements=movements,
        page=page,
        page_size=page_size,
        total=total,
    )


async def get_valuation(
    db: AsyncSession,
    tenant_id: str,
    category_id: str | None,
    warehouse_id: str | None,
) -> ValuationResponse:
    filters = ["p.tenant_id = :tid", "p.is_active = true"]
    params: dict = {"tid": tenant_id}

    if category_id:
        filters.append("p.category_id = :cid")
        params["cid"] = category_id

    where_p = " AND ".join(filters)

    wh_join = ""
    if warehouse_id:
        wh_join = "AND sb.warehouse_id = :wid"
        params["wid"] = warehouse_id

    rows = (
        await db.execute(
            text(
                f"SELECT p.id, p.sku, p.name, p.current_cpp, "
                f"COALESCE(SUM(sb.physical_qty), 0) AS total_qty "
                f"FROM products p "
                f"LEFT JOIN stock_balances sb ON sb.product_id = p.id AND sb.tenant_id = p.tenant_id {wh_join} "
                f"WHERE {where_p} "
                f"GROUP BY p.id, p.sku, p.name, p.current_cpp "
                f"ORDER BY p.sku"
            ),
            params,
        )
    ).fetchall()

    details = []
    total_val = Decimal("0")
    for r in rows:
        qty = Decimal(str(r.total_qty))
        cpp = Decimal(str(r.current_cpp))
        val = qty * cpp
        total_val += val
        details.append(ValuationDetail(product_id=str(r.id), sku=r.sku, name=r.name, total_qty=qty, current_cpp=cpp, total_value=val))

    return ValuationResponse(total_valuation=total_val, details=details)


async def _build_snapshot(tenant_id: str, body: SnapshotCreate) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await session.execute(text("SET LOCAL app.current_tenant = :tid"), {"tid": tenant_id})
        rows = (
            await session.execute(
                text(
                    "SELECT p.id AS product_id, p.current_cpp, "
                    "COALESCE(SUM(sb.physical_qty), 0) AS total_qty "
                    "FROM products p "
                    "LEFT JOIN stock_balances sb ON sb.product_id = p.id AND sb.tenant_id = p.tenant_id "
                    "WHERE p.tenant_id = :tid AND p.is_active = true "
                    "GROUP BY p.id, p.current_cpp"
                ),
                {"tid": tenant_id},
            )
        ).fetchall()

        now = datetime.now(timezone.utc)
        for r in rows:
            qty = Decimal(str(r.total_qty))
            cpp = Decimal(str(r.current_cpp))
            await session.execute(
                text(
                    "INSERT INTO valuation_snapshots "
                    "(id, tenant_id, period, product_id, snapshot_qty, snapshot_cpp, total_value, description, created_at) "
                    "VALUES (:id, :tid, :period, :pid, :qty, :cpp, :val, :desc, :now)"
                ),
                {
                    "id": str(uuid4()),
                    "tid": tenant_id,
                    "period": body.period,
                    "pid": str(r.product_id),
                    "qty": qty,
                    "cpp": cpp,
                    "val": qty * cpp,
                    "desc": body.description,
                    "now": now,
                },
            )
        await session.commit()


async def create_snapshot(
    db: AsyncSession,
    tenant_id: str,
    body: SnapshotCreate,
    background_tasks: BackgroundTasks,
) -> dict:
    background_tasks.add_task(_build_snapshot, tenant_id, body)
    return {"message": "Snapshot en proceso", "period": body.period}


async def list_snapshots(
    db: AsyncSession,
    tenant_id: str,
    period: str | None,
) -> list[SnapshotResponse]:
    params: dict = {"tid": tenant_id}
    extra = ""
    if period:
        extra = "AND period = :period"
        params["period"] = period

    rows = (
        await db.execute(
            text(
                f"SELECT id, period, product_id, snapshot_qty, snapshot_cpp, total_value, description, created_at "
                f"FROM valuation_snapshots WHERE tenant_id = :tid {extra} ORDER BY created_at DESC"
            ),
            params,
        )
    ).fetchall()

    return [
        SnapshotResponse(
            id=str(r.id),
            period=r.period,
            product_id=str(r.product_id),
            snapshot_qty=Decimal(str(r.snapshot_qty)),
            snapshot_cpp=Decimal(str(r.snapshot_cpp)),
            total_value=Decimal(str(r.total_value)),
            description=r.description,
            created_at=r.created_at,
        )
        for r in rows
    ]


async def get_low_stock(
    db: AsyncSession,
    tenant_id: str,
    warehouse_id: str | None,
    category_id: str | None,
    page: int,
    page_size: int,
) -> LowStockResponse:
    filters = ["p.tenant_id = :tid", "p.is_active = true", "p.low_stock_alert_enabled = true"]
    params: dict = {"tid": tenant_id}

    if category_id:
        filters.append("p.category_id = :cid")
        params["cid"] = category_id

    wh_join = ""
    if warehouse_id:
        wh_join = "AND sb.warehouse_id = :wid"
        params["wid"] = warehouse_id

    where_p = " AND ".join(filters)

    # Obtener todos los productos con alerta de stock bajo
    rows = (
        await db.execute(
            text(
                f"SELECT p.id, p.sku, p.name, p.reorder_point, "
                f"COALESCE(SUM(sb.available_qty), 0) AS available_qty "
                f"FROM products p "
                f"LEFT JOIN stock_balances sb ON sb.product_id = p.id AND sb.tenant_id = p.tenant_id {wh_join} "
                f"WHERE {where_p} "
                f"GROUP BY p.id, p.sku, p.name, p.reorder_point "
                f"HAVING COALESCE(SUM(sb.available_qty), 0) <= p.reorder_point "
                f"ORDER BY (p.reorder_point - COALESCE(SUM(sb.available_qty), 0)) DESC "
                f"LIMIT :lim OFFSET :off"
            ),
            {**params, "lim": page_size, "off": (page - 1) * page_size},
        )
    ).fetchall()

    # Contar total con subquery
    count_rows = (
        await db.execute(
            text(
                f"SELECT COUNT(*) FROM ("
                f"SELECT p.id "
                f"FROM products p "
                f"LEFT JOIN stock_balances sb ON sb.product_id = p.id AND sb.tenant_id = p.tenant_id {wh_join} "
                f"WHERE {where_p} "
                f"GROUP BY p.id, p.reorder_point "
                f"HAVING COALESCE(SUM(sb.available_qty), 0) <= p.reorder_point"
                f") sub"
            ),
            params,
        )
    ).scalar()
    total = int(count_rows or 0)

    return LowStockResponse(
        data=[
            LowStockItem(
                product_id=str(r.id),
                sku=r.sku,
                name=r.name,
                available_qty=Decimal(str(r.available_qty)),
                reorder_point=Decimal(str(r.reorder_point)),
                deficit=Decimal(str(r.reorder_point)) - Decimal(str(r.available_qty)),
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_expiring_batches(
    db: AsyncSession,
    tenant_id: str,
    days_ahead: int,
) -> ExpiringBatchesResponse:
    rows = (
        await db.execute(
            text(
                "SELECT b.id, b.batch_number, b.product_id, b.expiry_date, b.initial_qty, "
                "p.sku, p.name, "
                "(b.expiry_date - CURRENT_DATE) AS days_remaining "
                "FROM batches b "
                "JOIN products p ON p.id = b.product_id "
                "WHERE b.tenant_id = :tid "
                "AND b.expiry_date IS NOT NULL "
                "AND b.expiry_date <= CURRENT_DATE + :days * INTERVAL '1 day' "
                "ORDER BY b.expiry_date ASC"
            ),
            {"tid": tenant_id, "days": days_ahead},
        )
    ).fetchall()

    data = [
        ExpiringBatch(
            batch_id=str(r.id),
            batch_number=r.batch_number,
            product_id=str(r.product_id),
            product_sku=r.sku,
            product_name=r.name,
            expiry_date=str(r.expiry_date),
            days_remaining=int(r.days_remaining),
            initial_qty=Decimal(str(r.initial_qty)),
        )
        for r in rows
    ]
    return ExpiringBatchesResponse(data=data, total=len(data), days_ahead=days_ahead)
