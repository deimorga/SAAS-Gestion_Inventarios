"""Tests RF-010 (Lotes/Seriales) + RF-024 (Validación Seriales)."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_product_with_tracking(db: AsyncSession, tenant_id: str, sku: str, track_lots: bool = True, track_serials: bool = False) -> dict:
    pid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, :name, 'UNIT', 0, 0, :ts, :tl, false, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": sku, "name": f"Product {sku}", "ts": track_serials, "tl": track_lots},
    )
    await db.commit()
    return {"id": pid, "tenant_id": tenant_id, "sku": sku}


@pytest.mark.asyncio
async def test_create_batch(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"LOT-{uuid.uuid4().hex[:6]}")
    resp = await client.post("/v1/batches", json={
        "product_id": product["id"],
        "batch_number": f"BATCH-001-{uuid.uuid4().hex[:4]}",
        "manufactured_date": "2026-01-01",
        "expiry_date": "2027-01-01",
        "initial_qty": "100",
    }, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["batch_number"].startswith("BATCH-001")
    assert data["expiry_date"] == "2027-01-01"


@pytest.mark.asyncio
async def test_create_batch_product_without_lots(client: AsyncClient, auth_headers_a, product_a):
    resp = await client.post("/v1/batches", json={
        "product_id": product_a["id"],
        "batch_number": "BATCH-NO-LOT",
        "initial_qty": "50",
    }, headers=auth_headers_a)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_batch_number_409(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"DUP-{uuid.uuid4().hex[:6]}")
    bn = f"DUP-BATCH-{uuid.uuid4().hex[:4]}"
    payload = {"product_id": product["id"], "batch_number": bn, "initial_qty": "10"}
    r1 = await client.post("/v1/batches", json=payload, headers=auth_headers_a)
    assert r1.status_code == 201
    r2 = await client.post("/v1/batches", json=payload, headers=auth_headers_a)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_batches(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"LSTB-{uuid.uuid4().hex[:6]}")
    await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"B-{uuid.uuid4().hex[:4]}", "initial_qty": "5"}, headers=auth_headers_a)
    resp = await client.get(f"/v1/batches?product_id={product['id']}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_batch(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"GETB-{uuid.uuid4().hex[:6]}")
    cr = await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"GB-{uuid.uuid4().hex[:4]}", "initial_qty": "1"}, headers=auth_headers_a)
    bid = cr.json()["id"]
    resp = await client.get(f"/v1/batches/{bid}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == bid


@pytest.mark.asyncio
async def test_batch_not_found(client: AsyncClient, auth_headers_a):
    resp = await client.get(f"/v1/batches/{uuid.uuid4()}", headers=auth_headers_a)
    assert resp.status_code == 404


# ── Seriales ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_serials_to_batch(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"SER-{uuid.uuid4().hex[:6]}", track_lots=True, track_serials=True)
    cr = await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"BS-{uuid.uuid4().hex[:4]}", "initial_qty": "3"}, headers=auth_headers_a)
    bid = cr.json()["id"]
    sn1, sn2 = f"SN-{uuid.uuid4().hex[:8]}", f"SN-{uuid.uuid4().hex[:8]}"
    resp = await client.post(f"/v1/batches/{bid}/serials", json={"serials": [{"serial_number": sn1}, {"serial_number": sn2}]}, headers=auth_headers_a)
    assert resp.status_code == 201
    assert len(resp.json()) == 2
    assert all(s["status"] == "AVAILABLE" for s in resp.json())


@pytest.mark.asyncio
async def test_duplicate_serial_409(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"DSN-{uuid.uuid4().hex[:6]}", track_lots=True, track_serials=True)
    cr = await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"BDS-{uuid.uuid4().hex[:4]}", "initial_qty": "2"}, headers=auth_headers_a)
    bid = cr.json()["id"]
    sn = f"DUPSER-{uuid.uuid4().hex[:8]}"
    await client.post(f"/v1/batches/{bid}/serials", json={"serials": [{"serial_number": sn}]}, headers=auth_headers_a)
    resp = await client.post(f"/v1/batches/{bid}/serials", json={"serials": [{"serial_number": sn}]}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_serials(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"LSNS-{uuid.uuid4().hex[:6]}", track_lots=True, track_serials=True)
    cr = await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"BLSN-{uuid.uuid4().hex[:4]}", "initial_qty": "2"}, headers=auth_headers_a)
    bid = cr.json()["id"]
    await client.post(f"/v1/batches/{bid}/serials", json={"serials": [{"serial_number": f"SN-{uuid.uuid4().hex[:8]}"}]}, headers=auth_headers_a)
    resp = await client.get(f"/v1/batches/{bid}/serials", headers=auth_headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_serial_status(client: AsyncClient, auth_headers_a, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"GSTS-{uuid.uuid4().hex[:6]}", track_lots=True, track_serials=True)
    cr = await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"BGST-{uuid.uuid4().hex[:4]}", "initial_qty": "1"}, headers=auth_headers_a)
    bid = cr.json()["id"]
    sn = f"STATUS-{uuid.uuid4().hex[:8]}"
    await client.post(f"/v1/batches/{bid}/serials", json={"serials": [{"serial_number": sn}]}, headers=auth_headers_a)
    resp = await client.get(f"/v1/serials/{sn}/status", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "AVAILABLE"
    assert data["is_available"] is True
    assert data["serial_number"] == sn


@pytest.mark.asyncio
async def test_serial_not_found(client: AsyncClient, auth_headers_a):
    resp = await client.get("/v1/serials/INEXISTENTE-XYZ/status", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_serial_tenant_isolation(client: AsyncClient, auth_headers_a, auth_headers_b, tenant_a, db):
    product = await _create_product_with_tracking(db, tenant_a["id"], f"TISO-{uuid.uuid4().hex[:6]}", track_lots=True, track_serials=True)
    cr = await client.post("/v1/batches", json={"product_id": product["id"], "batch_number": f"BISO-{uuid.uuid4().hex[:4]}", "initial_qty": "1"}, headers=auth_headers_a)
    bid = cr.json()["id"]
    sn = f"ISO-{uuid.uuid4().hex[:8]}"
    await client.post(f"/v1/batches/{bid}/serials", json={"serials": [{"serial_number": sn}]}, headers=auth_headers_a)
    resp = await client.get(f"/v1/serials/{sn}/status", headers=auth_headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_batch_unauthenticated(client: AsyncClient):
    resp = await client.get("/v1/batches")
    assert resp.status_code == 401
