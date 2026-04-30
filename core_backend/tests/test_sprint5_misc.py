"""Tests RF-021 (Repack) + RF-023 (Vencimiento) + RF-028 (Channel Allocation)."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from tests.conftest import _create_warehouse, _create_zone, _create_product_simple


async def _stock_receipt(client, auth_headers, warehouse_id, zone_id, product_id, qty: float = 100.0):
    resp = await client.post("/v1/transactions/receipts", json={
        "reference_type": "PO",
        "reference_id": f"TEST-{uuid.uuid4().hex[:6]}",
        "reason_code": "COMPRA",
        "warehouse_id": warehouse_id,
        "zone_id": zone_id,
        "items": [{"product_id": product_id, "quantity": str(qty), "unit_cost": "10.00"}],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── RF-021 Repack ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repack_success(client: AsyncClient, auth_headers_a, db, tenant_a):
    wh = await _create_warehouse(db, tenant_a["id"], f"WH-RP-{uuid.uuid4().hex[:6]}")
    zn = await _create_zone(db, tenant_a["id"], wh["id"], f"ZRP-{uuid.uuid4().hex[:6]}")
    src = await _create_product_simple(db, tenant_a["id"], f"SRC-{uuid.uuid4().hex[:6]}")
    tgt = await _create_product_simple(db, tenant_a["id"], f"TGT-{uuid.uuid4().hex[:6]}")

    await _stock_receipt(client, auth_headers_a, wh["id"], zn["id"], src["id"], qty=10)

    resp = await client.post("/v1/transactions/repacks", json={
        "reference_id": f"REPACK-{uuid.uuid4().hex[:6]}",
        "warehouse_id": wh["id"],
        "zone_id": zn["id"],
        "source_items": [{"product_id": src["id"], "quantity": "5"}],
        "target_items": [{"product_id": tgt["id"], "quantity": "10"}],
    }, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["items_processed"] == 2


@pytest.mark.asyncio
async def test_repack_insufficient_stock(client: AsyncClient, auth_headers_a, db, tenant_a):
    wh = await _create_warehouse(db, tenant_a["id"], f"WH-RPI-{uuid.uuid4().hex[:6]}")
    zn = await _create_zone(db, tenant_a["id"], wh["id"], f"ZRPI-{uuid.uuid4().hex[:6]}")
    src = await _create_product_simple(db, tenant_a["id"], f"SRCI-{uuid.uuid4().hex[:6]}")
    tgt = await _create_product_simple(db, tenant_a["id"], f"TGTI-{uuid.uuid4().hex[:6]}")

    await _stock_receipt(client, auth_headers_a, wh["id"], zn["id"], src["id"], qty=2)

    resp = await client.post("/v1/transactions/repacks", json={
        "reference_id": "REPACK-FAIL",
        "warehouse_id": wh["id"],
        "zone_id": zn["id"],
        "source_items": [{"product_id": src["id"], "quantity": "999"}],
        "target_items": [{"product_id": tgt["id"], "quantity": "1"}],
    }, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_repack_unauthenticated(client: AsyncClient):
    resp = await client.post("/v1/transactions/repacks", json={
        "reference_id": "X", "warehouse_id": str(uuid.uuid4()), "zone_id": str(uuid.uuid4()),
        "source_items": [], "target_items": [],
    })
    assert resp.status_code == 401


# ── RF-023 Control de Vencimiento ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expiring_report(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_simple(db, tenant_a["id"], f"EXP-{uuid.uuid4().hex[:6]}")
    # Insert batch via DB to avoid having to create a lot-tracked product
    await db.execute(text(
        "UPDATE products SET track_lots=true WHERE id=:id"
    ), {"id": product["id"]})
    await db.commit()

    near_expiry = "2026-05-10"
    await client.post("/v1/batches", json={
        "product_id": product["id"],
        "batch_number": f"EXP-BATCH-{uuid.uuid4().hex[:4]}",
        "initial_qty": "50",
        "expiry_date": near_expiry,
    }, headers=auth_headers_a)

    resp = await client.get("/v1/reports/expiring?days_ahead=365", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "days_ahead" in data
    assert data["days_ahead"] == 365


@pytest.mark.asyncio
async def test_expiring_report_unauthenticated(client: AsyncClient):
    resp = await client.get("/v1/reports/expiring")
    assert resp.status_code == 401


# ── RF-028 Channel Allocation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_channel_allocation(client: AsyncClient, auth_headers_a, product_a, zone_a):
    resp = await client.post("/v1/channel-allocations", json={
        "product_id": product_a["id"],
        "zone_id": zone_a["id"],
        "channel": "WEB",
        "allocated_qty": "50",
    }, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["channel"] == "WEB"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_channel_allocation_duplicate_409(client: AsyncClient, auth_headers_a, product_a, zone_a):
    payload = {"product_id": product_a["id"], "zone_id": zone_a["id"], "channel": "POS", "allocated_qty": "10"}
    r1 = await client.post("/v1/channel-allocations", json=payload, headers=auth_headers_a)
    assert r1.status_code == 201
    r2 = await client.post("/v1/channel-allocations", json=payload, headers=auth_headers_a)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_channel_allocations(client: AsyncClient, auth_headers_a, product_a, zone_a):
    await client.post("/v1/channel-allocations", json={
        "product_id": product_a["id"], "zone_id": zone_a["id"], "channel": "B2B", "allocated_qty": "25"
    }, headers=auth_headers_a)
    resp = await client.get(f"/v1/channel-allocations?product_id={product_a['id']}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(a["channel"] == "B2B" for a in resp.json())


@pytest.mark.asyncio
async def test_update_channel_allocation(client: AsyncClient, auth_headers_a, product_a, zone_a):
    cr = await client.post("/v1/channel-allocations", json={
        "product_id": product_a["id"], "zone_id": zone_a["id"], "channel": "MOBILE", "allocated_qty": "20"
    }, headers=auth_headers_a)
    aid = cr.json()["id"]
    resp = await client.patch(f"/v1/channel-allocations/{aid}", json={"allocated_qty": "35"}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["allocated_qty"] == "35.0000"


@pytest.mark.asyncio
async def test_delete_channel_allocation(client: AsyncClient, auth_headers_a, product_a, zone_a):
    cr = await client.post("/v1/channel-allocations", json={
        "product_id": product_a["id"], "zone_id": zone_a["id"], "channel": "WHOLESALE", "allocated_qty": "5"
    }, headers=auth_headers_a)
    aid = cr.json()["id"]
    resp = await client.delete(f"/v1/channel-allocations/{aid}", headers=auth_headers_a)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_channel_allocation_tenant_isolation(client: AsyncClient, auth_headers_a, auth_headers_b, product_a, zone_a):
    cr = await client.post("/v1/channel-allocations", json={
        "product_id": product_a["id"], "zone_id": zone_a["id"], "channel": "MARKETPLACE", "allocated_qty": "15"
    }, headers=auth_headers_a)
    aid = cr.json()["id"]
    resp = await client.delete(f"/v1/channel-allocations/{aid}", headers=auth_headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_channel_allocation_unauthenticated(client: AsyncClient):
    resp = await client.get("/v1/channel-allocations")
    assert resp.status_code == 401
