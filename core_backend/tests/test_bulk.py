"""Tests para el Bulk Engine (Sprint 4: T-403 y T-404)."""
import pytest
import pytest_asyncio

from tests.conftest import (
    _create_product_simple,
    _create_warehouse,
    _create_zone,
    uid,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _do_receipt(client, headers, wh_id, zone_id, prod_id, qty=50, cost=1000):
    resp = await client.post(
        "/v1/transactions/receipts",
        json={
            "warehouse_id": wh_id,
            "zone_id": zone_id,
            "reference_type": "PO",
            "reference_id": f"PO-{uid()[:6]}",
            "reason_code": "COMPRA",
            "items": [{"product_id": prod_id, "quantity": qty, "unit_cost": cost}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _receipt_payload(wh_id, zone_id, prod_id, qty=10, cost=500):
    return {
        "warehouse_id": wh_id,
        "zone_id": zone_id,
        "reference_type": "BULK_PO",
        "reference_id": f"BPO-{uid()[:6]}",
        "reason_code": "COMPRA",
        "items": [{"product_id": prod_id, "quantity": qty, "unit_cost": cost}],
    }


def _issue_payload(wh_id, zone_id, prod_id, qty=5):
    return {
        "warehouse_id": wh_id,
        "zone_id": zone_id,
        "reference_type": "BULK_SO",
        "reference_id": f"BSO-{uid()[:6]}",
        "reason_code": "VENTA",
        "items": [{"product_id": prod_id, "quantity": qty}],
    }


def _transfer_payload(src_wh, src_z, tgt_wh, tgt_z, prod_id, qty=3):
    return {
        "source_warehouse_id": src_wh,
        "source_zone_id": src_z,
        "target_warehouse_id": tgt_wh,
        "target_zone_id": tgt_z,
        "reference_id": f"BTR-{uid()[:6]}",
        "items": [{"product_id": prod_id, "quantity": qty}],
    }


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def bulk_setup(db, client, tenant_a, auth_headers_a):
    wh1 = await _create_warehouse(db, tenant_a["id"], f"BLK-WH1-{uid()[:6]}")
    wh2 = await _create_warehouse(db, tenant_a["id"], f"BLK-WH2-{uid()[:6]}")
    z1 = await _create_zone(db, tenant_a["id"], wh1["id"], f"BZ1-{uid()[:6]}")
    z2 = await _create_zone(db, tenant_a["id"], wh2["id"], f"BZ2-{uid()[:6]}")
    p1 = await _create_product_simple(db, tenant_a["id"], f"BSKU1-{uid()[:6]}")
    p2 = await _create_product_simple(db, tenant_a["id"], f"BSKU2-{uid()[:6]}")
    # Stock inicial en wh1/z1
    await _do_receipt(client, auth_headers_a, wh1["id"], z1["id"], p1["id"], 100)
    await _do_receipt(client, auth_headers_a, wh1["id"], z1["id"], p2["id"], 100)
    yield {"wh1": wh1, "wh2": wh2, "z1": z1, "z2": z2, "p1": p1, "p2": p2}


# ── T-403: Bulk Receipts ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_receipts_all_ok(client, auth_headers_a, bulk_setup):
    s = bulk_setup
    body = {
        "items": [
            _receipt_payload(s["wh1"]["id"], s["z1"]["id"], s["p1"]["id"], qty=5),
            _receipt_payload(s["wh1"]["id"], s["z1"]["id"], s["p2"]["id"], qty=8),
        ]
    }
    resp = await client.post("/v1/bulk/receipts", json=body, headers=auth_headers_a)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0
    for r in data["results"]:
        assert r["status"] == "ok"
        assert r["transaction_id"] is not None


@pytest.mark.asyncio
async def test_bulk_receipts_partial_failure(client, auth_headers_a, bulk_setup):
    """Un ítem con almacén inválido falla sin afectar el ítem válido."""
    s = bulk_setup
    body = {
        "items": [
            _receipt_payload(s["wh1"]["id"], s["z1"]["id"], s["p1"]["id"], qty=3),
            _receipt_payload(uid(), uid(), s["p1"]["id"], qty=3),  # almacén inválido
        ]
    }
    resp = await client.post("/v1/bulk/receipts", json=body, headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    assert data["results"][0]["status"] == "ok"
    assert data["results"][1]["status"] == "error"
    assert data["results"][1]["detail"] is not None


@pytest.mark.asyncio
async def test_bulk_receipts_empty_list(client, auth_headers_a):
    resp = await client.post("/v1/bulk/receipts", json={"items": []}, headers=auth_headers_a)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_receipts_requires_auth(client, bulk_setup):
    s = bulk_setup
    body = {"items": [_receipt_payload(s["wh1"]["id"], s["z1"]["id"], s["p1"]["id"])]}
    resp = await client.post("/v1/bulk/receipts", json=body, headers={})
    assert resp.status_code == 401


# ── T-403: Bulk Issues ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_issues_all_ok(client, auth_headers_a, bulk_setup):
    s = bulk_setup
    body = {
        "items": [
            _issue_payload(s["wh1"]["id"], s["z1"]["id"], s["p1"]["id"], qty=5),
            _issue_payload(s["wh1"]["id"], s["z1"]["id"], s["p2"]["id"], qty=5),
        ]
    }
    resp = await client.post("/v1/bulk/issues", json=body, headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["succeeded"] == 2
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_issues_insufficient_stock(client, auth_headers_a, bulk_setup):
    """Un ítem con stock insuficiente falla sin afectar al otro."""
    s = bulk_setup
    body = {
        "items": [
            _issue_payload(s["wh1"]["id"], s["z1"]["id"], s["p1"]["id"], qty=5),
            _issue_payload(s["wh1"]["id"], s["z1"]["id"], s["p2"]["id"], qty=9999),
        ]
    }
    resp = await client.post("/v1/bulk/issues", json=body, headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    assert data["results"][1]["status"] == "error"


@pytest.mark.asyncio
async def test_bulk_result_format(client, auth_headers_a, bulk_setup):
    """Verificar el formato exacto del resultado parcial."""
    s = bulk_setup
    body = {
        "items": [
            _receipt_payload(s["wh1"]["id"], s["z1"]["id"], s["p1"]["id"], qty=1),
        ]
    }
    resp = await client.post("/v1/bulk/receipts", json=body, headers=auth_headers_a)
    data = resp.json()
    assert "total" in data
    assert "succeeded" in data
    assert "failed" in data
    assert "results" in data
    r = data["results"][0]
    assert "index" in r
    assert "status" in r
    assert r["index"] == 0


# ── T-404: Bulk Transfers ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_transfers_all_ok(client, auth_headers_a, bulk_setup):
    s = bulk_setup
    body = {
        "items": [
            _transfer_payload(s["wh1"]["id"], s["z1"]["id"], s["wh2"]["id"], s["z2"]["id"], s["p1"]["id"], qty=5),
            _transfer_payload(s["wh1"]["id"], s["z1"]["id"], s["wh2"]["id"], s["z2"]["id"], s["p2"]["id"], qty=5),
        ]
    }
    resp = await client.post("/v1/bulk/transfers", json=body, headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["succeeded"] == 2
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_transfers_partial_failure(client, auth_headers_a, bulk_setup):
    """Una transferencia con stock insuficiente falla individualmente."""
    s = bulk_setup
    body = {
        "items": [
            _transfer_payload(s["wh1"]["id"], s["z1"]["id"], s["wh2"]["id"], s["z2"]["id"], s["p1"]["id"], qty=2),
            _transfer_payload(s["wh1"]["id"], s["z1"]["id"], s["wh2"]["id"], s["z2"]["id"], s["p2"]["id"], qty=9999),
        ]
    }
    resp = await client.post("/v1/bulk/transfers", json=body, headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 1


@pytest.mark.asyncio
async def test_bulk_transfers_requires_auth(client, bulk_setup):
    s = bulk_setup
    body = {
        "items": [
            _transfer_payload(s["wh1"]["id"], s["z1"]["id"], s["wh2"]["id"], s["z2"]["id"], s["p1"]["id"])
        ]
    }
    resp = await client.post("/v1/bulk/transfers", json=body, headers={})
    assert resp.status_code == 401
