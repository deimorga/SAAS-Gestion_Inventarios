"""Tests del Motor Transaccional — RF-016..022 (T-202 a T-207)."""
import pytest
from httpx import AsyncClient
from sqlalchemy import text


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _receipt(client, headers, warehouse_id, zone_id, product_id, qty, cost=1000.0, reference_id="PO-001"):
    return await client.post(
        "/v1/transactions/receipts",
        json={
            "reference_type": "PURCHASE_ORDER",
            "reference_id": reference_id,
            "reason_code": "COMPRA_PROVEEDOR",
            "warehouse_id": warehouse_id,
            "zone_id": zone_id,
            "items": [{"product_id": product_id, "quantity": qty, "unit_cost": cost}],
        },
        headers=headers,
    )


async def _issue(client, headers, warehouse_id, zone_id, product_id, qty, reference_id="SO-001"):
    return await client.post(
        "/v1/transactions/issues",
        json={
            "reference_type": "SALES_ORDER",
            "reference_id": reference_id,
            "reason_code": "VENTA_CLIENTE",
            "warehouse_id": warehouse_id,
            "zone_id": zone_id,
            "items": [{"product_id": product_id, "quantity": qty}],
        },
        headers=headers,
    )


# ── Receipts (RF-016) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receipt_creates_stock(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a):
    resp = await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 50, cost=500.0)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["transaction_type"] == "RECEIPT"
    assert body["status"] == "COMPLETED"
    assert body["items_processed"] == 1


@pytest.mark.asyncio
async def test_receipt_updates_cpp(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db):
    """CPP se actualiza con la fórmula de costo promedio ponderado."""
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 100, cost=200.0)
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 100, cost=400.0)

    result = await db.execute(text("SELECT current_cpp FROM products WHERE id = :id"), {"id": product_a["id"]})
    cpp = float(result.scalar_one())
    # Expected: (100*200 + 100*400) / 200 = 300.0
    assert abs(cpp - 300.0) < 0.01, f"CPP esperado ~300, obtenido {cpp}"


@pytest.mark.asyncio
async def test_receipt_appends_ledger(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 10, reference_id="PO-LEDGER")
    result = await db.execute(
        text("SELECT COUNT(*) FROM inventory_ledger WHERE product_id = :pid AND reference_id = 'PO-LEDGER'"),
        {"pid": product_a["id"]},
    )
    assert result.scalar_one() >= 1


@pytest.mark.asyncio
async def test_receipt_invalid_warehouse(client: AsyncClient, auth_headers_a, zone_a, product_a):
    resp = await _receipt(
        client, auth_headers_a,
        "00000000-0000-0000-0000-000000000000",
        zone_a["id"], product_a["id"], 5,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_receipt_invalid_product(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    resp = await _receipt(
        client, auth_headers_a,
        warehouse_a["id"], zone_a["id"],
        "00000000-0000-0000-0000-000000000000", 5,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_receipt_return_in(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a):
    """RF-020: Devolución de cliente como RETURN_IN."""
    resp = await client.post(
        "/v1/transactions/receipts",
        json={
            "reference_type": "RETURN_IN",
            "reference_id": "RMA-001",
            "reason_code": "DEVOLUCION_CLIENTE",
            "warehouse_id": warehouse_a["id"],
            "zone_id": zone_a["id"],
            "items": [{"product_id": product_a["id"], "quantity": 3, "unit_cost": 500}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 201


# ── Issues (RF-017) ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_issue_reduces_stock(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 20, cost=100.0)
    resp = await _issue(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 5)
    assert resp.status_code == 201, resp.text
    assert resp.json()["transaction_type"] == "ISSUE"


@pytest.mark.asyncio
async def test_issue_insufficient_stock(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 5, cost=100.0)
    resp = await _issue(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 100)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_issue_scrap_loss(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db):
    """RF-022: Baja/scrap registra movement_type=SCRAP."""
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 10, cost=100.0)
    resp = await client.post(
        "/v1/transactions/issues",
        json={
            "reference_type": "SCRAP",
            "reference_id": "SCRAP-001",
            "reason_code": "SCRAP_LOSS",
            "warehouse_id": warehouse_a["id"],
            "zone_id": zone_a["id"],
            "items": [{"product_id": product_a["id"], "quantity": 2}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 201

    result = await db.execute(
        text("SELECT movement_type FROM inventory_ledger WHERE reference_id = 'SCRAP-001'")
    )
    movement = result.scalar_one_or_none()
    assert movement == "SCRAP"


@pytest.mark.asyncio
async def test_issue_requires_auth(client: AsyncClient, warehouse_a, zone_a, product_a):
    resp = await _issue(client, {}, warehouse_a["id"], zone_a["id"], product_a["id"], 1)
    assert resp.status_code == 401


# ── Transfers (RF-018) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transfer_moves_stock(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db, tenant_a):
    from tests.conftest import _create_warehouse, _create_zone
    wh2 = await _create_warehouse(db, tenant_a["id"], "WH-A-02")
    z2 = await _create_zone(db, tenant_a["id"], wh2["id"], "ZONE-A-02")

    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 30, cost=200.0)

    resp = await client.post(
        "/v1/transactions/transfers",
        json={
            "reference_id": "TR-001",
            "source_warehouse_id": warehouse_a["id"],
            "source_zone_id": zone_a["id"],
            "target_warehouse_id": wh2["id"],
            "target_zone_id": z2["id"],
            "items": [{"product_id": product_a["id"], "quantity": 10}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["transaction_type"] == "TRANSFER"

    # Source balance should be 20, dest should be 10
    src = await db.execute(
        text("SELECT physical_qty FROM stock_balances WHERE product_id=:pid AND zone_id=:zid"),
        {"pid": product_a["id"], "zid": zone_a["id"]},
    )
    dst = await db.execute(
        text("SELECT physical_qty FROM stock_balances WHERE product_id=:pid AND zone_id=:zid"),
        {"pid": product_a["id"], "zid": z2["id"]},
    )
    assert float(src.scalar_one()) == 20.0
    assert float(dst.scalar_one()) == 10.0

    # Cleanup
    await db.execute(text("DELETE FROM warehouses WHERE id = :id"), {"id": wh2["id"]})
    await db.commit()


@pytest.mark.asyncio
async def test_transfer_insufficient_source_stock(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db, tenant_a):
    from tests.conftest import _create_warehouse, _create_zone
    wh2 = await _create_warehouse(db, tenant_a["id"], "WH-A-03")
    z2 = await _create_zone(db, tenant_a["id"], wh2["id"], "ZONE-A-03")

    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 5, cost=100.0)

    resp = await client.post(
        "/v1/transactions/transfers",
        json={
            "reference_id": "TR-FAIL",
            "source_warehouse_id": warehouse_a["id"],
            "source_zone_id": zone_a["id"],
            "target_warehouse_id": wh2["id"],
            "target_zone_id": z2["id"],
            "items": [{"product_id": product_a["id"], "quantity": 100}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 409

    await db.execute(text("DELETE FROM warehouses WHERE id = :id"), {"id": wh2["id"]})
    await db.commit()


@pytest.mark.asyncio
async def test_transfer_produces_two_ledger_entries(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db, tenant_a):
    from tests.conftest import _create_warehouse, _create_zone
    wh2 = await _create_warehouse(db, tenant_a["id"], "WH-A-04")
    z2 = await _create_zone(db, tenant_a["id"], wh2["id"], "ZONE-A-04")

    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 20, cost=100.0)

    resp = await client.post(
        "/v1/transactions/transfers",
        json={
            "reference_id": "TR-LEDGER",
            "source_warehouse_id": warehouse_a["id"],
            "source_zone_id": zone_a["id"],
            "target_warehouse_id": wh2["id"],
            "target_zone_id": z2["id"],
            "items": [{"product_id": product_a["id"], "quantity": 5}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    tx_id = resp.json()["transaction_id"]

    result = await db.execute(
        text("SELECT movement_type FROM inventory_ledger WHERE transaction_id = :tid ORDER BY movement_type"),
        {"tid": tx_id},
    )
    movements = sorted(r[0] for r in result.fetchall())
    assert movements == ["TRANSFER_IN", "TRANSFER_OUT"]

    await db.execute(text("DELETE FROM warehouses WHERE id = :id"), {"id": wh2["id"]})
    await db.commit()


# ── Adjustments (RF-019) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_adjustment_sets_new_qty(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 50, cost=100.0)

    resp = await client.post(
        "/v1/transactions/adjustments",
        json={
            "reference_id": "CONTEO-001",
            "reason_code": "CONTEO_FISICO",
            "warehouse_id": warehouse_a["id"],
            "zone_id": zone_a["id"],
            "items": [{"product_id": product_a["id"], "new_qty": 45}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["transaction_type"] == "ADJUSTMENT"

    result = await db.execute(
        text("SELECT physical_qty FROM stock_balances WHERE product_id=:pid AND zone_id=:zid"),
        {"pid": product_a["id"], "zid": zone_a["id"]},
    )
    assert float(result.scalar_one()) == 45.0


@pytest.mark.asyncio
async def test_adjustment_ledger_movement_type(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 10, cost=100.0)
    await client.post(
        "/v1/transactions/adjustments",
        json={
            "reference_id": "CONTEO-002",
            "reason_code": "CONTEO_FISICO",
            "warehouse_id": warehouse_a["id"],
            "zone_id": zone_a["id"],
            "items": [{"product_id": product_a["id"], "new_qty": 8}],
        },
        headers=auth_headers_a,
    )
    result = await db.execute(
        text("SELECT movement_type, qty_change FROM inventory_ledger WHERE reference_id='CONTEO-002'")
    )
    row = result.fetchone()
    assert row[0] == "ADJUSTMENT"
    assert float(row[1]) == -2.0


# ── Stock Balances (GET) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stock_balances_query(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 25, cost=100.0)
    resp = await client.get(
        "/v1/stock/balances",
        params={"product_id": product_a["id"]},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    entry = next(e for e in data if e["product_id"] == product_a["id"])
    assert float(entry["physical_qty"]) > 0


@pytest.mark.asyncio
async def test_stock_balances_tenant_isolation(client: AsyncClient, auth_headers_a, warehouse_b, zone_a, product_a, db, tenant_b):
    """Tenant A no puede ver saldos del Tenant B."""
    from tests.conftest import _create_zone, _create_product_simple
    z_b = await _create_zone(db, tenant_b["id"], warehouse_b["id"], "ZB-ISO")
    prod_b = await _create_product_simple(db, tenant_b["id"], "SKU-B-ISO")

    await db.execute(
        text(
            "INSERT INTO stock_balances (id, tenant_id, product_id, warehouse_id, zone_id, "
            "physical_qty, reserved_qty, available_qty, version, updated_at) "
            "VALUES (gen_random_uuid(), :tid, :pid, :wid, :zid, 99, 0, 99, 1, now())"
        ),
        {"tid": tenant_b["id"], "pid": prod_b["id"], "wid": warehouse_b["id"], "zid": z_b["id"]},
    )
    await db.commit()

    resp = await client.get(
        "/v1/stock/balances",
        params={"product_id": prod_b["id"]},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


# ── Ledger (GET) ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ledger_query(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a):
    await _receipt(client, auth_headers_a, warehouse_a["id"], zone_a["id"], product_a["id"], 7, reference_id="PO-LEDGER-Q")
    resp = await client.get(
        "/v1/ledger",
        params={"product_id": product_a["id"]},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(e["product_id"] == product_a["id"] for e in data)


@pytest.mark.asyncio
async def test_ledger_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/ledger")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stock_balances_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/stock/balances")
    assert resp.status_code == 401
