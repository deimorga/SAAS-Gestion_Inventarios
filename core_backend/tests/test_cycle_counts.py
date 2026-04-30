"""Tests para Inventario Cíclico (Sprint 4: T-405 y T-406)."""

import pytest
import pytest_asyncio

from tests.conftest import (
    _create_product_simple,
    _create_warehouse,
    _create_zone,
    uid,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _do_receipt(client, headers, wh_id, zone_id, prod_id, qty, cost=1000):
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


async def _create_session(client, headers, wh_id, label="Test Conteo", apply=False):
    return await client.post(
        "/v1/cycle-counts",
        json={"warehouse_id": wh_id, "label": label, "apply_adjustments": apply},
        headers=headers,
    )


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def cc_setup(db, client, tenant_a, auth_headers_a):
    wh = await _create_warehouse(db, tenant_a["id"], f"CC-WH-{uid()[:6]}")
    zone = await _create_zone(db, tenant_a["id"], wh["id"], f"CC-Z-{uid()[:6]}")
    prod = await _create_product_simple(db, tenant_a["id"], f"CC-SKU-{uid()[:6]}")
    # Stock inicial: 20 unidades
    await _do_receipt(client, auth_headers_a, wh["id"], zone["id"], prod["id"], 20)
    yield {"wh": wh, "zone": zone, "prod": prod}


# ── T-405: Crear sesión y snapshot ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_success(client, auth_headers_a, cc_setup):
    resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "OPEN"
    assert data["warehouse_id"] == cc_setup["wh"]["id"]
    assert len(data["items"]) >= 1

    item = next(i for i in data["items"] if i["product_id"] == cc_setup["prod"]["id"])
    assert float(item["expected_qty"]) == 20.0
    assert item["counted_qty"] is None
    assert item["variance"] is None


@pytest.mark.asyncio
async def test_create_session_invalid_warehouse(client, auth_headers_a):
    resp = await _create_session(client, auth_headers_a, uid())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_sessions(client, auth_headers_a, cc_setup):
    await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    resp = await client.get("/v1/cycle-counts", headers=auth_headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_sessions_filter_by_status(client, auth_headers_a, cc_setup):
    await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    resp = await client.get("/v1/cycle-counts?status=OPEN", headers=auth_headers_a)
    assert resp.status_code == 200
    assert all(s["status"] == "OPEN" for s in resp.json())


@pytest.mark.asyncio
async def test_get_session_detail(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    sid = create_resp.json()["id"]

    resp = await client.get(f"/v1/cycle-counts/{sid}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_get_session_not_found(client, auth_headers_a):
    resp = await client.get(f"/v1/cycle-counts/{uid()}", headers=auth_headers_a)
    assert resp.status_code == 404


# ── T-406: Conteo y cierre ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_count(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    session = create_resp.json()
    sid = session["id"]
    item = next(i for i in session["items"] if i["product_id"] == cc_setup["prod"]["id"])

    resp = await client.patch(
        f"/v1/cycle-counts/{sid}/items/{item['id']}",
        json={"counted_qty": 18.0},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert float(data["counted_qty"]) == 18.0
    assert float(data["expected_qty"]) == 20.0
    assert float(data["variance"]) == pytest.approx(-2.0)


@pytest.mark.asyncio
async def test_record_count_zero_variance(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    session = create_resp.json()
    sid = session["id"]
    item = next(i for i in session["items"] if i["product_id"] == cc_setup["prod"]["id"])

    resp = await client.patch(
        f"/v1/cycle-counts/{sid}/items/{item['id']}",
        json={"counted_qty": 20.0},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    assert float(resp.json()["variance"]) == 0.0


@pytest.mark.asyncio
async def test_record_count_item_not_found(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    sid = create_resp.json()["id"]

    resp = await client.patch(
        f"/v1/cycle-counts/{sid}/items/{uid()}",
        json={"counted_qty": 10.0},
        headers=auth_headers_a,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_close_session_no_adjustments(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"], apply=False)
    sid = create_resp.json()["id"]

    resp = await client.post(
        f"/v1/cycle-counts/{sid}/close",
        json={"reference_id": "CIERRE-TEST-001"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "CLOSED"
    assert data["closed_at"] is not None


@pytest.mark.asyncio
async def test_close_session_with_adjustments(client, auth_headers_a, cc_setup):
    """Con apply_adjustments=true, el cierre ajusta stock_balances."""
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"], apply=True)
    session = create_resp.json()
    sid = session["id"]
    item = next(i for i in session["items"] if i["product_id"] == cc_setup["prod"]["id"])

    # Registrar conteo: 15 (varianza -5)
    await client.patch(
        f"/v1/cycle-counts/{sid}/items/{item['id']}",
        json={"counted_qty": 15.0},
        headers=auth_headers_a,
    )

    resp = await client.post(
        f"/v1/cycle-counts/{sid}/close",
        json={"reference_id": "CIERRE-ADJ-001"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CLOSED"

    # Verificar que stock_balances refleja el ajuste
    bal_resp = await client.get(
        f"/v1/stock/balances?product_id={cc_setup['prod']['id']}&zone_id={cc_setup['zone']['id']}",
        headers=auth_headers_a,
    )
    balance = bal_resp.json()["data"][0]
    assert float(balance["physical_qty"]) == pytest.approx(15.0)
    assert float(balance["available_qty"]) == pytest.approx(15.0)


@pytest.mark.asyncio
async def test_close_session_already_closed(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    sid = create_resp.json()["id"]

    await client.post(f"/v1/cycle-counts/{sid}/close", json={"reference_id": "REF-001"}, headers=auth_headers_a)
    # Segundo cierre debe fallar
    resp = await client.post(f"/v1/cycle-counts/{sid}/close", json={"reference_id": "REF-002"}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_record_count_on_closed_session(client, auth_headers_a, cc_setup):
    create_resp = await _create_session(client, auth_headers_a, cc_setup["wh"]["id"])
    session = create_resp.json()
    sid = session["id"]
    item = session["items"][0]

    await client.post(f"/v1/cycle-counts/{sid}/close", json={"reference_id": "REF-X"}, headers=auth_headers_a)
    resp = await client.patch(
        f"/v1/cycle-counts/{sid}/items/{item['id']}",
        json={"counted_qty": 5.0},
        headers=auth_headers_a,
    )
    assert resp.status_code == 409


# ── Auth y aislamiento ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cycle_count_requires_auth(client, cc_setup):
    resp = await _create_session(client, {}, cc_setup["wh"]["id"])
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cycle_count_tenant_isolation(client, auth_headers_b, cc_setup):
    """Tenant B no puede ver sesiones del Tenant A."""
    resp = await client.get("/v1/cycle-counts", headers=auth_headers_b)
    assert resp.status_code == 200
    assert resp.json() == []
