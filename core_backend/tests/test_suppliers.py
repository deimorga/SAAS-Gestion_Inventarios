"""Tests RF-011 (Proveedores) + RF-012 (Costos Reposición)."""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_supplier(client: AsyncClient, auth_headers_a):
    resp = await client.post("/v1/suppliers", json={
        "code": f"PROV-{uuid.uuid4().hex[:6]}",
        "name": "Proveedor Test S.A.",
        "email": "contacto@proveedor.com",
        "currency": "MXN",
        "payment_terms_days": 30,
    }, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Proveedor Test S.A."
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_supplier_duplicate_code(client: AsyncClient, auth_headers_a):
    code = f"DUP-{uuid.uuid4().hex[:6]}"
    payload = {"code": code, "name": "Proveedor A", "currency": "MXN", "payment_terms_days": 30}
    r1 = await client.post("/v1/suppliers", json=payload, headers=auth_headers_a)
    assert r1.status_code == 201
    r2 = await client.post("/v1/suppliers", json=payload, headers=auth_headers_a)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_suppliers(client: AsyncClient, auth_headers_a):
    code = f"LST-{uuid.uuid4().hex[:6]}"
    await client.post("/v1/suppliers", json={"code": code, "name": "Para Listar", "currency": "MXN", "payment_terms_days": 15}, headers=auth_headers_a)
    resp = await client.get("/v1/suppliers", headers=auth_headers_a)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(s["code"] == code for s in resp.json())


@pytest.mark.asyncio
async def test_get_supplier(client: AsyncClient, auth_headers_a):
    code = f"GET-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Para Get", "currency": "MXN", "payment_terms_days": 0}, headers=auth_headers_a)
    sid = cr.json()["id"]
    resp = await client.get(f"/v1/suppliers/{sid}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


@pytest.mark.asyncio
async def test_update_supplier(client: AsyncClient, auth_headers_a):
    code = f"UPD-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Original", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    resp = await client.patch(f"/v1/suppliers/{sid}", json={"name": "Actualizado", "payment_terms_days": 45}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Actualizado"
    assert resp.json()["payment_terms_days"] == 45


@pytest.mark.asyncio
async def test_deactivate_supplier(client: AsyncClient, auth_headers_a):
    code = f"DEL-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "A Eliminar", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    resp = await client.delete(f"/v1/suppliers/{sid}", headers=auth_headers_a)
    assert resp.status_code == 204
    # Ahora no aparece en lista activa
    lst = await client.get("/v1/suppliers?is_active=true", headers=auth_headers_a)
    assert not any(s["id"] == sid for s in lst.json())


@pytest.mark.asyncio
async def test_supplier_tenant_isolation(client: AsyncClient, auth_headers_a, auth_headers_b):
    code = f"ISO-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Solo A", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    resp = await client.get(f"/v1/suppliers/{sid}", headers=auth_headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_supplier_unauthenticated(client: AsyncClient):
    resp = await client.get("/v1/suppliers")
    assert resp.status_code == 401


# ── RF-012 Costos Reposición ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_supplier_product(client: AsyncClient, auth_headers_a, product_a):
    code = f"COST-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Proveedor Costos", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    resp = await client.post(f"/v1/suppliers/{sid}/products", json={
        "product_id": product_a["id"],
        "unit_cost": "15.50",
        "currency": "MXN",
        "lead_time_days": 5,
        "moq": "10",
        "is_preferred": True,
    }, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["unit_cost"] == "15.5000"
    assert data["is_preferred"] is True


@pytest.mark.asyncio
async def test_list_supplier_products(client: AsyncClient, auth_headers_a, product_a):
    code = f"LSPR-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Proveedor Lista", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    await client.post(f"/v1/suppliers/{sid}/products", json={
        "product_id": product_a["id"], "unit_cost": "20.00", "currency": "MXN",
        "lead_time_days": 3, "moq": "1", "is_preferred": False,
    }, headers=auth_headers_a)
    resp = await client.get(f"/v1/suppliers/{sid}/products", headers=auth_headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_update_supplier_product(client: AsyncClient, auth_headers_a, product_a):
    code = f"UPSP-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Proveedor Update", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    sp = await client.post(f"/v1/suppliers/{sid}/products", json={
        "product_id": product_a["id"], "unit_cost": "10.00", "currency": "MXN",
        "lead_time_days": 1, "moq": "1", "is_preferred": False,
    }, headers=auth_headers_a)
    spid = sp.json()["id"]
    resp = await client.patch(f"/v1/suppliers/{sid}/products/{spid}", json={"unit_cost": "12.00", "is_preferred": True}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["unit_cost"] == "12.0000"
    assert resp.json()["is_preferred"] is True


@pytest.mark.asyncio
async def test_delete_supplier_product(client: AsyncClient, auth_headers_a, product_a):
    code = f"DLSP-{uuid.uuid4().hex[:6]}"
    cr = await client.post("/v1/suppliers", json={"code": code, "name": "Proveedor Del", "currency": "MXN", "payment_terms_days": 30}, headers=auth_headers_a)
    sid = cr.json()["id"]
    sp = await client.post(f"/v1/suppliers/{sid}/products", json={
        "product_id": product_a["id"], "unit_cost": "5.00", "currency": "MXN",
        "lead_time_days": 0, "moq": "1", "is_preferred": False,
    }, headers=auth_headers_a)
    spid = sp.json()["id"]
    resp = await client.delete(f"/v1/suppliers/{sid}/products/{spid}", headers=auth_headers_a)
    assert resp.status_code == 204
