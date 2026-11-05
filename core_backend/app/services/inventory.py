"""Motor transaccional de inventario.

Reglas de oro:
- inventory_ledger es append-only (no UPDATE ni DELETE).
- stock_balances usa OCC (optimistic concurrency control) con campo version.
- Las transferencias son atómicas: salida + entrada en una misma transacción SQL.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch
from app.models.bin import Bin
from app.models.inventory_ledger import InventoryLedger
from app.models.product import Product
from app.models.stock_balance import StockBalance
from app.models.transaction import Transaction
from app.models.warehouse import Warehouse
from app.models.zone import Zone
from app.services.traceability import (
    balance_supplier,
    ensure_batch,
    eq_or_null,
    get_bin_in_zone,
    get_supplier_of_tenant,
    next_document_number,
    opt_str,
    require_lot,
)
from app.schemas.inventory import (
    AdjustmentRequest,
    IssueRequest,
    LedgerEntryResponse,
    ReceiptRequest,
    RepackRequest,
    StockBalanceResponse,
    TransactionResponse,
    TransactionType,
    TransferRequest,
)
from app.schemas.common import PaginatedResponse, PaginationMeta

_MAX_OCC_RETRIES = 3


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_active_warehouse(db: AsyncSession, warehouse_id: str, tenant_id: str) -> Warehouse:
    result = await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.tenant_id == tenant_id, Warehouse.is_active.is_(True))
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Almacén no encontrado o inactivo")
    return wh


async def _get_active_zone(db: AsyncSession, zone_id: str, warehouse_id: str, tenant_id: str) -> Zone:
    result = await db.execute(
        select(Zone).where(Zone.id == zone_id, Zone.warehouse_id == warehouse_id, Zone.tenant_id == tenant_id, Zone.is_active.is_(True))
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona no encontrada o inactiva")
    return zone


async def _get_active_product(db: AsyncSession, product_id: str, tenant_id: str) -> Product:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id, Product.is_active.is_(True))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Producto {product_id} no encontrado o inactivo")
    return product


async def _get_or_create_balance(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    warehouse_id: str,
    zone_id: str,
    lot_number: str | None,
    bin_id: str | None = None,
    supplier_id: str | None = None,
) -> StockBalance:
    """Saldo exacto de producto + zona + bin + lote + proveedor (lo crea en cero si no existe).

    Sin bin ni proveedor es exactamente la clave de siempre (producto + zona + lote).
    """
    bin_id = opt_str(bin_id)
    supplier_id = balance_supplier(lot_number, supplier_id)
    result = await db.execute(
        select(StockBalance).where(
            StockBalance.tenant_id == tenant_id,
            StockBalance.product_id == product_id,
            StockBalance.zone_id == zone_id,
            eq_or_null(StockBalance.lot_number, lot_number),
            eq_or_null(StockBalance.bin_id, bin_id),
            eq_or_null(StockBalance.supplier_id, supplier_id),
        )
    )
    balance = result.scalar_one_or_none()
    if not balance:
        balance = StockBalance(
            tenant_id=tenant_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            zone_id=zone_id,
            lot_number=lot_number,
            bin_id=bin_id,
            supplier_id=supplier_id,
            physical_qty=Decimal("0"),
            reserved_qty=Decimal("0"),
            available_qty=Decimal("0"),
            version=1,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(balance)
        await db.flush()
    return balance


async def _find_existing_balance(
    db: AsyncSession,
    tenant_id: str,
    product: Product,
    zone_id: str,
    lot_number: str | None,
    bin_id: str | None,
    supplier_id: str | None,
) -> StockBalance | None:
    """Saldo del que sale o que se ajusta. El proveedor solo es obligatorio si hace falta.

    Con lote y sin proveedor se busca entre todos los proveedores: si el número existe
    de uno solo, es ese; si existe de varios, la operación es ambigua y se pide
    supplier_id (pasa solo cuando dos proveedores traen el mismo número de lote).
    """
    query = select(StockBalance).where(
        StockBalance.tenant_id == tenant_id,
        StockBalance.product_id == product.id,
        StockBalance.zone_id == zone_id,
        eq_or_null(StockBalance.lot_number, lot_number),
        eq_or_null(StockBalance.bin_id, opt_str(bin_id)),
    )
    if not lot_number or supplier_id is not None:
        query = query.where(eq_or_null(StockBalance.supplier_id, balance_supplier(lot_number, supplier_id)))
    rows = list((await db.execute(query)).scalars().all())
    if len(rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El lote {lot_number} del producto {product.sku} existe de varios proveedores en esta "
                "ubicación: indique supplier_id en el ítem."
            ),
        )
    return rows[0] if rows else None


async def _apply_balance_change(
    db: AsyncSession,
    balance: StockBalance,
    qty_delta: Decimal,
    allow_negative: bool = False,
) -> None:
    """OCC update: validates version match, retries up to _MAX_OCC_RETRIES times."""
    for attempt in range(_MAX_OCC_RETRIES):
        old_version = balance.version
        new_physical = balance.physical_qty + qty_delta
        if not allow_negative and new_physical < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente: disponible {balance.available_qty}, solicitado {abs(qty_delta)}",
            )
        new_available = new_physical - balance.reserved_qty

        rows = await db.execute(
            text(
                "UPDATE stock_balances "
                "SET physical_qty = :phys, available_qty = :avail, version = :new_ver, updated_at = now() "
                "WHERE id = :id AND version = :old_ver"
            ),
            {
                "phys": float(new_physical),
                "avail": float(new_available),
                "new_ver": old_version + 1,
                "old_ver": old_version,
                "id": balance.id,
            },
        )
        if rows.rowcount == 1:  # type: ignore[attr-defined]
            balance.physical_qty = new_physical
            balance.available_qty = new_available
            balance.version = old_version + 1
            return

        # Concurrent modification — re-read and retry
        await db.refresh(balance)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Conflicto de concurrencia al actualizar el saldo. Reintente la operación.",
    )


async def _update_product_cpp(
    db: AsyncSession,
    product: Product,
    tenant_id: str,
    new_qty: Decimal,
    unit_cost: Decimal,
) -> None:
    """Recalculate weighted average cost after a receipt."""
    total_result = await db.execute(
        select(func.sum(StockBalance.physical_qty)).where(
            StockBalance.product_id == product.id,
            StockBalance.tenant_id == tenant_id,
        )
    )
    old_total_qty = (total_result.scalar_one_or_none() or Decimal("0"))
    # old_total_qty already includes the qty we just added; subtract it back
    pre_receipt_qty = old_total_qty - new_qty
    if pre_receipt_qty < 0:
        pre_receipt_qty = Decimal("0")

    if pre_receipt_qty + new_qty == 0:
        new_cpp = unit_cost
    else:
        new_cpp = (pre_receipt_qty * product.current_cpp + new_qty * unit_cost) / (pre_receipt_qty + new_qty)

    await db.execute(
        text("UPDATE products SET current_cpp = :cpp, updated_at = now() WHERE id = :id"),
        {"cpp": float(new_cpp), "id": product.id},
    )
    product.current_cpp = new_cpp


def _make_ledger_entry(
    tenant_id: str,
    transaction_id: str,
    product_id: str,
    warehouse_id: str,
    zone_id: str,
    movement_type: str,
    qty_change: Decimal,
    unit_cost: Decimal | None,
    reference_type: str,
    reference_id: str,
    reason_code: str,
    lot_number: str | None = None,
    serial_number: str | None = None,
    expiry_date=None,
    bin_id=None,
    supplier_id=None,
) -> InventoryLedger:
    return InventoryLedger(
        bin_id=opt_str(bin_id),
        supplier_id=opt_str(supplier_id),
        tenant_id=tenant_id,
        transaction_id=transaction_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        zone_id=zone_id,
        movement_type=movement_type,
        qty_change=qty_change,
        unit_cost=unit_cost,
        lot_number=lot_number,
        serial_number=serial_number,
        expiry_date=expiry_date,
        reference_type=reference_type,
        reference_id=reference_id,
        reason_code=reason_code,
        created_at=datetime.now(timezone.utc),
    )


def _make_transaction(
    tenant_id: str,
    transaction_type: TransactionType,
    reference_type: str,
    reference_id: str,
    reason_code: str,
    items_processed: int,
    created_by: str | None = None,
) -> Transaction:
    return Transaction(
        tenant_id=tenant_id,
        transaction_type=transaction_type.value,
        reference_type=reference_type,
        reference_id=reference_id,
        reason_code=reason_code,
        status="COMPLETED",
        items_processed=items_processed,
        created_at=datetime.now(timezone.utc),
        created_by=created_by,
    )


def _tx_response(tx: Transaction) -> TransactionResponse:
    return TransactionResponse(
        transaction_id=tx.id,
        transaction_type=TransactionType(tx.transaction_type),
        timestamp=tx.created_at,
        status=tx.status,
        items_processed=tx.items_processed,
        document_number=tx.document_number,
    )


# ── Receipts (RF-016 + RF-020 RETURN_IN) ─────────────────────────────────────

async def process_receipt(
    body: ReceiptRequest, db: AsyncSession, tenant_id: str, created_by: str | None = None
) -> TransactionResponse:
    await _get_active_warehouse(db, str(body.warehouse_id), tenant_id)
    await _get_active_zone(db, str(body.zone_id), str(body.warehouse_id), tenant_id)
    await get_supplier_of_tenant(db, body.supplier_id, tenant_id)

    # Validar todo antes de escribir: lote obligatorio, bin de la zona, proveedor del tenant.
    prepared = []
    for item in body.items:
        product = await _get_active_product(db, str(item.product_id), tenant_id)
        require_lot(product, item.lot_number)
        await get_bin_in_zone(db, item.bin_id, body.zone_id, tenant_id)
        await get_supplier_of_tenant(db, item.supplier_id, tenant_id)
        supplier_id = opt_str(item.supplier_id or body.supplier_id)
        prepared.append((item, product, supplier_id))

    tx = _make_transaction(
        tenant_id, TransactionType.RECEIPT,
        body.reference_type, body.reference_id, body.reason_code,
        len(body.items), created_by,
    )
    tx.document_number = await next_document_number(db, tenant_id)
    db.add(tx)
    await db.flush()

    for item, product, supplier_id in prepared:
        unit_cost = item.unit_cost or Decimal("0")

        balance = await _get_or_create_balance(
            db, tenant_id, str(item.product_id),
            str(body.warehouse_id), str(body.zone_id), item.lot_number,
            bin_id=item.bin_id, supplier_id=supplier_id,
        )
        await _apply_balance_change(db, balance, item.quantity)
        await _update_product_cpp(db, product, tenant_id, item.quantity, unit_cost)

        # La entrada crea (o reutiliza) el lote: hereda proveedor y vencimiento.
        if product.track_lots and item.lot_number:
            await ensure_batch(
                db, tenant_id, str(item.product_id), item.lot_number,
                balance_supplier(item.lot_number, supplier_id), item.expiry_date, item.quantity,
            )

        entry = _make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=str(body.warehouse_id), zone_id=str(body.zone_id),
            movement_type="RECEIPT", qty_change=item.quantity, unit_cost=unit_cost,
            reference_type=body.reference_type, reference_id=body.reference_id, reason_code=body.reason_code,
            lot_number=item.lot_number, serial_number=item.serial_number, expiry_date=item.expiry_date,
            bin_id=item.bin_id, supplier_id=supplier_id,
        )
        db.add(entry)

    await db.commit()
    await db.refresh(tx)
    return _tx_response(tx)


# ── Issues (RF-017 + RF-022 SCRAP) ───────────────────────────────────────────

async def process_issue(
    body: IssueRequest, db: AsyncSession, tenant_id: str, created_by: str | None = None
) -> TransactionResponse:
    await _get_active_warehouse(db, str(body.warehouse_id), tenant_id)
    await _get_active_zone(db, str(body.zone_id), str(body.warehouse_id), tenant_id)

    # Validate all items have enough stock before touching anything
    prepared = []
    for item in body.items:
        product = await _get_active_product(db, str(item.product_id), tenant_id)
        await get_bin_in_zone(db, item.bin_id, body.zone_id, tenant_id)
        await get_supplier_of_tenant(db, item.supplier_id, tenant_id)
        balance = await _find_existing_balance(
            db, tenant_id, product, str(body.zone_id), item.lot_number, item.bin_id, item.supplier_id,
        )
        available = balance.available_qty if balance else Decimal("0")
        if available < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para producto {item.product_id}: disponible {available}, solicitado {item.quantity}",
            )
        prepared.append((item, product, balance))

    tx = _make_transaction(
        tenant_id, TransactionType.ISSUE,
        body.reference_type, body.reference_id, body.reason_code,
        len(body.items), created_by,
    )
    db.add(tx)
    await db.flush()

    for item, product, balance in prepared:
        await _apply_balance_change(db, balance, -item.quantity)

        movement = "SCRAP" if body.reason_code in ("SCRAP_LOSS", "MERMA", "BAJA") else "ISSUE"
        entry = _make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=str(body.warehouse_id), zone_id=str(body.zone_id),
            movement_type=movement, qty_change=-item.quantity, unit_cost=product.current_cpp,
            reference_type=body.reference_type, reference_id=body.reference_id, reason_code=body.reason_code,
            lot_number=item.lot_number, serial_number=item.serial_number,
            bin_id=balance.bin_id, supplier_id=balance.supplier_id or item.supplier_id,
        )
        db.add(entry)

    await db.commit()
    await db.refresh(tx)
    return _tx_response(tx)


# ── Transfers (RF-018) ────────────────────────────────────────────────────────

async def process_transfer(
    body: TransferRequest, db: AsyncSession, tenant_id: str, created_by: str | None = None
) -> TransactionResponse:
    await _get_active_warehouse(db, str(body.source_warehouse_id), tenant_id)
    await _get_active_zone(db, str(body.source_zone_id), str(body.source_warehouse_id), tenant_id)
    await _get_active_warehouse(db, str(body.target_warehouse_id), tenant_id)
    await _get_active_zone(db, str(body.target_zone_id), str(body.target_warehouse_id), tenant_id)

    # Pre-validate stock on source
    prepared = []
    for item in body.items:
        product = await _get_active_product(db, str(item.product_id), tenant_id)
        require_lot(product, item.lot_number)
        await get_bin_in_zone(db, item.from_bin_id, body.source_zone_id, tenant_id)
        await get_bin_in_zone(db, item.to_bin_id, body.target_zone_id, tenant_id)
        await get_supplier_of_tenant(db, item.supplier_id, tenant_id)
        src_balance = await _find_existing_balance(
            db, tenant_id, product, str(body.source_zone_id), item.lot_number, item.from_bin_id, item.supplier_id,
        )
        if src_balance is None or src_balance.available_qty < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente en origen para producto {item.product_id}",
            )
        prepared.append((item, product, src_balance))

    tx = _make_transaction(
        tenant_id, TransactionType.TRANSFER,
        body.reference_type, body.reference_id, body.reason_code,
        len(body.items), created_by,
    )
    db.add(tx)
    await db.flush()

    for item, product, src_balance in prepared:
        # El lote viaja con su proveedor; solo cambian la zona y/o el bin.
        dst_balance = await _get_or_create_balance(
            db, tenant_id, str(item.product_id),
            str(body.target_warehouse_id), str(body.target_zone_id), item.lot_number,
            bin_id=item.to_bin_id, supplier_id=src_balance.supplier_id,
        )

        await _apply_balance_change(db, src_balance, -item.quantity)
        await _apply_balance_change(db, dst_balance, item.quantity)

        db.add(_make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=str(body.source_warehouse_id), zone_id=str(body.source_zone_id),
            movement_type="TRANSFER_OUT", qty_change=-item.quantity, unit_cost=product.current_cpp,
            reference_type=body.reference_type, reference_id=body.reference_id, reason_code=body.reason_code,
            lot_number=item.lot_number, bin_id=item.from_bin_id, supplier_id=src_balance.supplier_id,
        ))
        db.add(_make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=str(body.target_warehouse_id), zone_id=str(body.target_zone_id),
            movement_type="TRANSFER_IN", qty_change=item.quantity, unit_cost=product.current_cpp,
            reference_type=body.reference_type, reference_id=body.reference_id, reason_code=body.reason_code,
            lot_number=item.lot_number, bin_id=item.to_bin_id, supplier_id=src_balance.supplier_id,
        ))

    await db.commit()
    await db.refresh(tx)
    return _tx_response(tx)


# ── Adjustments (RF-019) ──────────────────────────────────────────────────────

async def process_adjustment(
    body: AdjustmentRequest, db: AsyncSession, tenant_id: str, created_by: str | None = None
) -> TransactionResponse:
    await _get_active_warehouse(db, str(body.warehouse_id), tenant_id)
    await _get_active_zone(db, str(body.zone_id), str(body.warehouse_id), tenant_id)

    prepared = []
    for item in body.items:
        product = await _get_active_product(db, str(item.product_id), tenant_id)
        require_lot(product, item.lot_number)
        await get_bin_in_zone(db, item.bin_id, body.zone_id, tenant_id)
        await get_supplier_of_tenant(db, item.supplier_id, tenant_id)
        prepared.append((item, product))

    tx = _make_transaction(
        tenant_id, TransactionType.ADJUSTMENT,
        "PHYSICAL_COUNT", body.reference_id, body.reason_code,
        len(body.items), created_by,
    )
    db.add(tx)
    await db.flush()

    for item, product in prepared:
        balance = await _find_existing_balance(
            db, tenant_id, product, str(body.zone_id), item.lot_number, item.bin_id, item.supplier_id,
        ) or await _get_or_create_balance(
            db, tenant_id, str(item.product_id),
            str(body.warehouse_id), str(body.zone_id), item.lot_number,
            bin_id=item.bin_id, supplier_id=item.supplier_id,
        )
        delta = item.new_qty - balance.physical_qty
        if delta == 0:
            continue

        await _apply_balance_change(db, balance, delta, allow_negative=True)

        db.add(_make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=str(body.warehouse_id), zone_id=str(body.zone_id),
            movement_type="ADJUSTMENT", qty_change=delta, unit_cost=product.current_cpp,
            reference_type="PHYSICAL_COUNT", reference_id=body.reference_id, reason_code=body.reason_code,
            lot_number=item.lot_number, bin_id=balance.bin_id, supplier_id=balance.supplier_id,
        ))

    await db.commit()
    await db.refresh(tx)
    return _tx_response(tx)


# ── Repack (RF-021) ───────────────────────────────────────────────────────────

async def process_repack(
    body: RepackRequest, db: AsyncSession, tenant_id: str, created_by: str | None = None
) -> TransactionResponse:
    """Consume source items and generate target items in the same zone (re-empaque)."""
    warehouse_id = str(body.warehouse_id)
    zone_id = str(body.zone_id)
    await _get_active_warehouse(db, warehouse_id, tenant_id)
    await _get_active_zone(db, zone_id, warehouse_id, tenant_id)

    # Validate source stock before touching anything
    for item in body.source_items:
        balance = await _get_or_create_balance(
            db, tenant_id, str(item.product_id), warehouse_id, zone_id, item.lot_number
        )
        if balance.available_qty < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para producto {item.product_id}: disponible {balance.available_qty}, solicitado {item.quantity}",
            )

    total_items = len(body.source_items) + len(body.target_items)
    tx = _make_transaction(
        tenant_id, TransactionType.ADJUSTMENT,
        "REPACK", body.reference_id, "REEMPAQUE", total_items, created_by,
    )
    db.add(tx)
    await db.flush()

    # Consume sources
    for item in body.source_items:
        product = await _get_active_product(db, str(item.product_id), tenant_id)
        balance = await _get_or_create_balance(
            db, tenant_id, str(item.product_id), warehouse_id, zone_id, item.lot_number
        )
        await _apply_balance_change(db, balance, -item.quantity)
        db.add(_make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=warehouse_id, zone_id=zone_id,
            movement_type="ISSUE", qty_change=-item.quantity, unit_cost=product.current_cpp,
            reference_type="REPACK", reference_id=body.reference_id, reason_code="REEMPAQUE",
            lot_number=item.lot_number,
        ))

    # Generate targets
    for item in body.target_items:
        product = await _get_active_product(db, str(item.product_id), tenant_id)
        balance = await _get_or_create_balance(
            db, tenant_id, str(item.product_id), warehouse_id, zone_id, item.lot_number
        )
        await _apply_balance_change(db, balance, item.quantity)
        await _update_product_cpp(db, product, tenant_id, item.quantity, product.current_cpp)
        db.add(_make_ledger_entry(
            tenant_id=tenant_id, transaction_id=tx.id,
            product_id=str(item.product_id), warehouse_id=warehouse_id, zone_id=zone_id,
            movement_type="RECEIPT", qty_change=item.quantity, unit_cost=product.current_cpp,
            reference_type="REPACK", reference_id=body.reference_id, reason_code="REEMPAQUE",
            lot_number=item.lot_number,
        ))

    await db.commit()
    await db.refresh(tx)
    return _tx_response(tx)


# ── Query: Stock Balances ─────────────────────────────────────────────────────

async def query_stock_balances(
    db: AsyncSession,
    tenant_id: str,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    zone_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    *,
    lot_number: str | None = None,
    bin_id: str | None = None,
    supplier_id: str | None = None,
) -> PaginatedResponse:
    # Vencimiento del lote: del registro del lote y, para lotes anteriores a que las
    # entradas crearan lotes, de la primera entrada con fecha en el ledger.
    ledger_expiry = (
        select(func.min(InventoryLedger.expiry_date))
        .where(
            InventoryLedger.tenant_id == StockBalance.tenant_id,
            InventoryLedger.product_id == StockBalance.product_id,
            InventoryLedger.lot_number == StockBalance.lot_number,
        )
        .correlate(StockBalance)
        .scalar_subquery()
    )
    q = (
        select(StockBalance, Bin.code, Bin.name, func.coalesce(Batch.expiry_date, ledger_expiry))
        .outerjoin(Bin, Bin.id == StockBalance.bin_id)
        .outerjoin(
            Batch,
            (Batch.tenant_id == StockBalance.tenant_id)
            & (Batch.product_id == StockBalance.product_id)
            & (Batch.batch_number == StockBalance.lot_number)
            & Batch.supplier_id.is_not_distinct_from(StockBalance.supplier_id),
        )
        .where(StockBalance.tenant_id == tenant_id)
    )
    if product_id:
        q = q.where(StockBalance.product_id == product_id)
    if warehouse_id:
        q = q.where(StockBalance.warehouse_id == warehouse_id)
    if zone_id:
        q = q.where(StockBalance.zone_id == zone_id)
    if lot_number:
        q = q.where(StockBalance.lot_number == lot_number)
    if bin_id:
        q = q.where(StockBalance.bin_id == str(bin_id))
    if supplier_id:
        q = q.where(StockBalance.supplier_id == str(supplier_id))

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(q.order_by(StockBalance.updated_at.desc()).offset(offset).limit(page_size))).all()

    data = []
    for balance, bin_code, bin_name, expiry_date in rows:
        item = StockBalanceResponse.model_validate(balance)
        item.bin_code, item.bin_name, item.expiry_date = bin_code, bin_name, expiry_date
        data.append(item)

    total_pages = max(1, -(-total // page_size))
    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total_items=total, total_pages=total_pages),
    )


# ── Query: Ledger ─────────────────────────────────────────────────────────────

async def query_ledger(
    db: AsyncSession,
    tenant_id: str,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    transaction_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    *,
    lot_number: str | None = None,
    zone_id: str | None = None,
    bin_id: str | None = None,
    supplier_id: str | None = None,
    reference_id: str | None = None,
    document_number: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedResponse:
    q = (
        select(InventoryLedger, Bin.code, Bin.name, Transaction.document_number)
        .outerjoin(Bin, Bin.id == InventoryLedger.bin_id)
        .outerjoin(Transaction, Transaction.id == InventoryLedger.transaction_id)
        .where(InventoryLedger.tenant_id == tenant_id)
    )
    if product_id:
        q = q.where(InventoryLedger.product_id == product_id)
    if warehouse_id:
        q = q.where(InventoryLedger.warehouse_id == warehouse_id)
    if transaction_id:
        q = q.where(InventoryLedger.transaction_id == transaction_id)
    if lot_number:
        q = q.where(InventoryLedger.lot_number == lot_number)
    if zone_id:
        q = q.where(InventoryLedger.zone_id == str(zone_id))
    if bin_id:
        q = q.where(InventoryLedger.bin_id == str(bin_id))
    if supplier_id:
        q = q.where(InventoryLedger.supplier_id == str(supplier_id))
    if reference_id:
        q = q.where(InventoryLedger.reference_id == reference_id)
    if document_number:
        q = q.where(Transaction.document_number == document_number)
    # Rango por día, inclusivo en ambos extremos (UTC).
    if date_from:
        q = q.where(InventoryLedger.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        next_day = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        q = q.where(InventoryLedger.created_at < next_day)

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(q.order_by(InventoryLedger.created_at.desc()).offset(offset).limit(page_size))).all()

    data = []
    for entry, bin_code, bin_name, doc_number in rows:
        item = LedgerEntryResponse.model_validate(entry)
        item.bin_code, item.bin_name, item.document_number = bin_code, bin_name, doc_number
        data.append(item)

    total_pages = max(1, -(-total // page_size))
    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total_items=total, total_pages=total_pages),
    )
