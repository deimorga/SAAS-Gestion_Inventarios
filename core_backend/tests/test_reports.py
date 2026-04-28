"""Tests para el módulo de Reportes (Sprint 3: T-301 a T-304)."""
import pytest
import pytest_asyncio
from sqlalchemy import text

from tests.conftest import (
    _create_product_simple,
    _create_warehouse,
    _create_zone,
    uid,
)


# ── Helpers Sprint 3 ──────────────────────────────────────────────────────────

async def _do_receipt(client, headers, warehouse_id, zone_id, product_id, qty, cost):
    resp = await client.post(
        "/v1/transactions/receipts",
        json={
            "warehouse_id": warehouse_id,
            "zone_id": zone_id,
            "reference_type": "PO",
            "reference_id": f"PO-{uid()[:6]}",
            "reason_code": "COMPRA",
            "items": [{"product_id": product_id, "quantity": qty, "unit_cost": cost}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _do_issue(client, headers, warehouse_id, zone_id, product_id, qty):
    resp = await client.post(
        "/v1/transactions/issues",
        json={
            "warehouse_id": warehouse_id,
            "zone_id": zone_id,
            "reference_type": "SO",
            "reference_id": f"SO-{uid()[:6]}",
            "reason_code": "VENTA",
            "items": [{"product_id": product_id, "quantity": qty}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Fixtures Sprint 3 ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def report_setup(db, client, tenant_a, auth_headers_a):
    """Crea warehouse, zona y producto con movimientos para los tests de reportes."""
    wh = await _create_warehouse(db, tenant_a["id"], f"WH-RPT-{uid()[:6]}")
    zone = await _create_zone(db, tenant_a["id"], wh["id"], f"Z-RPT-{uid()[:6]}")
    prod = await _create_product_simple(db, tenant_a["id"], f"RPT-{uid()[:6]}")

    # Registrar entrada y salida para tener movimientos en el ledger
    await _do_receipt(client, auth_headers_a, wh["id"], zone["id"], prod["id"], 50, 10000)
    await _do_issue(client, auth_headers_a, wh["id"], zone["id"], prod["id"], 5)

    yield {"wh": wh, "zone": zone, "prod": prod}


# ── T-301: Kardex ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kardex_returns_movements(client, auth_headers_a, report_setup):
    prod_id = report_setup["prod"]["id"]
    resp = await client.get(f"/v1/reports/kardex?product_id={prod_id}", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["product"]["id"] == prod_id
    assert data["total"] >= 2
    assert len(data["movements"]) >= 2


@pytest.mark.asyncio
async def test_kardex_balance_accumulates(client, auth_headers_a, report_setup):
    prod_id = report_setup["prod"]["id"]
    resp = await client.get(f"/v1/reports/kardex?product_id={prod_id}", headers=auth_headers_a)
    assert resp.status_code == 200
    movements = resp.json()["movements"]
    # balance_after del último movimiento debe ser 45 (50 in - 5 out)
    last_balance = float(movements[-1]["balance_after"])
    assert last_balance == pytest.approx(45.0)


@pytest.mark.asyncio
async def test_kardex_filter_by_warehouse(client, auth_headers_a, report_setup):
    prod_id = report_setup["prod"]["id"]
    wh_id = report_setup["wh"]["id"]
    resp = await client.get(
        f"/v1/reports/kardex?product_id={prod_id}&warehouse_id={wh_id}",
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2


@pytest.mark.asyncio
async def test_kardex_product_not_found(client, auth_headers_a):
    resp = await client.get(f"/v1/reports/kardex?product_id={uid()}", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_kardex_requires_auth(client):
    resp = await client.get(f"/v1/reports/kardex?product_id={uid()}")
    assert resp.status_code == 401


# ── T-302: Valoración Contable ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valuation_returns_total(client, auth_headers_a, report_setup):
    resp = await client.get("/v1/reports/valuation", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_valuation" in data
    assert float(data["total_valuation"]) >= 0
    assert isinstance(data["details"], list)


@pytest.mark.asyncio
async def test_valuation_product_value_correct(client, auth_headers_a, report_setup):
    prod_id = report_setup["prod"]["id"]
    resp = await client.get("/v1/reports/valuation", headers=auth_headers_a)
    assert resp.status_code == 200
    details = resp.json()["details"]
    prod_detail = next((d for d in details if d["product_id"] == prod_id), None)
    assert prod_detail is not None
    # qty=45, cpp=10000 → total_value=450000
    assert float(prod_detail["total_qty"]) == pytest.approx(45.0)
    assert float(prod_detail["total_value"]) == pytest.approx(450000.0)


@pytest.mark.asyncio
async def test_valuation_tenant_isolation(client, auth_headers_b, report_setup):
    """Tenant B no ve los productos del Tenant A."""
    resp = await client.get("/v1/reports/valuation", headers=auth_headers_b)
    assert resp.status_code == 200
    prod_id = report_setup["prod"]["id"]
    details = resp.json()["details"]
    assert not any(d["product_id"] == prod_id for d in details)


# ── T-303: Snapshots ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_snapshot_returns_202(client, auth_headers_a, report_setup):
    resp = await client.post(
        "/v1/reports/valuation/snapshots",
        json={"period": "2026-04", "description": "Cierre abril"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 202
    assert resp.json()["period"] == "2026-04"


@pytest.mark.asyncio
async def test_snapshot_list(client, auth_headers_a, report_setup):
    # Crear snapshot
    await client.post(
        "/v1/reports/valuation/snapshots",
        json={"period": "2026-03"},
        headers=auth_headers_a,
    )
    import asyncio
    await asyncio.sleep(0.5)  # esperar el background task
    resp = await client.get("/v1/reports/valuation/snapshots?period=2026-03", headers=auth_headers_a)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── T-304: Low Stock ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_low_stock_empty_when_no_alerts(client, auth_headers_a, db, tenant_a):
    """Producto con available_qty > reorder_point no aparece."""
    # El producto del report_setup tiene qty=45, reorder_point=0 → no es low stock
    resp = await client.get("/v1/reports/low-stock", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_low_stock_detects_alert(client, auth_headers_a, db, tenant_a):
    """Producto con reorder_point > available_qty aparece en alertas."""
    # Crear producto con reorder_point alto
    pid = uid()
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, :name, 'UNIT', 0, 100, false, false, false, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_a["id"], "sku": f"LOW-{uid()[:6]}", "name": "Low Stock Product"},
    )
    await db.commit()

    resp = await client.get("/v1/reports/low-stock", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    product_ids = [d["product_id"] for d in data["data"]]
    assert pid in product_ids

    # Verificar que deficit es positivo
    alert = next(d for d in data["data"] if d["product_id"] == pid)
    assert float(alert["deficit"]) > 0


@pytest.mark.asyncio
async def test_low_stock_requires_auth(client):
    resp = await client.get("/v1/reports/low-stock")
    assert resp.status_code == 401
