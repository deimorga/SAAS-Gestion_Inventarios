"""Tests de CRUD de Productos (T-107)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_product_success(client: AsyncClient, auth_headers_a):
    resp = await client.post(
        "/v1/products",
        json={"sku": "PROD-001", "name": "Monitor 24 IPS", "base_uom": "UNIT", "reorder_point": 5},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sku"] == "PROD-001"
    assert body["name"] == "Monitor 24 IPS"
    assert body["is_active"] is True
    assert body["is_kit"] is False
    assert float(body["current_cpp"]) == 0.0


@pytest.mark.asyncio
async def test_create_product_duplicate_sku(client: AsyncClient, auth_headers_a):
    payload = {"sku": "DUP-SKU-001", "name": "Producto Original", "base_uom": "UNIT"}
    await client.post("/v1/products", json=payload, headers=auth_headers_a)
    resp = await client.post("/v1/products", json=payload, headers=auth_headers_a)
    assert resp.status_code == 409
    assert "SKU" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_product_invalid_sku(client: AsyncClient, auth_headers_a):
    resp = await client.post(
        "/v1/products",
        json={"sku": "INVALID SKU!", "name": "Test", "base_uom": "UNIT"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_invalid_category(client: AsyncClient, auth_headers_a):
    resp = await client.post(
        "/v1/products",
        json={"sku": "CAT-ERR-001", "name": "Test", "base_uom": "UNIT", "category_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_products(client: AsyncClient, auth_headers_a):
    await client.post("/v1/products", json={"sku": "LIST-001", "name": "Alpha", "base_uom": "UNIT"}, headers=auth_headers_a)
    await client.post("/v1/products", json={"sku": "LIST-002", "name": "Beta", "base_uom": "KG"}, headers=auth_headers_a)

    resp = await client.get("/v1/products", headers=auth_headers_a)
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "pagination" in body
    assert body["pagination"]["total_items"] >= 2


@pytest.mark.asyncio
async def test_list_products_search(client: AsyncClient, auth_headers_a):
    await client.post("/v1/products", json={"sku": "SRCH-001", "name": "Teclado Mecánico", "base_uom": "UNIT"}, headers=auth_headers_a)
    resp = await client.get("/v1/products?search=Teclado", headers=auth_headers_a)
    assert resp.status_code == 200
    skus = [p["sku"] for p in resp.json()["data"]]
    assert "SRCH-001" in skus


@pytest.mark.asyncio
async def test_get_product_detail(client: AsyncClient, auth_headers_a):
    create = await client.post("/v1/products", json={"sku": "DET-001", "name": "Mouse", "base_uom": "UNIT"}, headers=auth_headers_a)
    pid = create.json()["id"]

    resp = await client.get(f"/v1/products/{pid}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


@pytest.mark.asyncio
async def test_get_product_not_found(client: AsyncClient, auth_headers_a):
    resp = await client.get("/v1/products/00000000-0000-0000-0000-000000000000", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_product(client: AsyncClient, auth_headers_a):
    create = await client.post("/v1/products", json={"sku": "PATCH-001", "name": "Original", "base_uom": "UNIT"}, headers=auth_headers_a)
    pid = create.json()["id"]

    resp = await client.patch(f"/v1/products/{pid}", json={"name": "Actualizado", "reorder_point": 20}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Actualizado"
    assert float(resp.json()["reorder_point"]) == 20.0


@pytest.mark.asyncio
async def test_delete_product_soft(client: AsyncClient, auth_headers_a):
    create = await client.post("/v1/products", json={"sku": "DEL-001", "name": "A eliminar", "base_uom": "UNIT"}, headers=auth_headers_a)
    pid = create.json()["id"]

    resp = await client.delete(f"/v1/products/{pid}", headers=auth_headers_a)
    assert resp.status_code == 204

    # Verificar soft delete: no aparece en listado por defecto
    list_resp = await client.get("/v1/products", headers=auth_headers_a)
    ids = [p["id"] for p in list_resp.json()["data"]]
    assert pid not in ids

    # Pero sí aparece si se pide is_active=false
    list_inactive = await client.get("/v1/products?is_active=false", headers=auth_headers_a)
    ids_inactive = [p["id"] for p in list_inactive.json()["data"]]
    assert pid in ids_inactive


# ── UOM tests (T-109) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_uom_crud(client: AsyncClient, auth_headers_a):
    create = await client.post("/v1/products", json={"sku": "UOM-001", "name": "Café", "base_uom": "KG"}, headers=auth_headers_a)
    pid = create.json()["id"]

    # Agregar conversión
    uom_resp = await client.post(
        f"/v1/products/{pid}/uom",
        json={"uom_code": "SACO", "conversion_factor": 50.0, "is_purchase_uom": True},
        headers=auth_headers_a,
    )
    assert uom_resp.status_code == 201
    assert uom_resp.json()["uom_code"] == "SACO"
    uom_id = uom_resp.json()["id"]

    # Listar
    list_resp = await client.get(f"/v1/products/{pid}/uom", headers=auth_headers_a)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Eliminar
    del_resp = await client.delete(f"/v1/products/{pid}/uom/{uom_id}", headers=auth_headers_a)
    assert del_resp.status_code == 204

    # Verificar eliminación
    list_after = await client.get(f"/v1/products/{pid}/uom", headers=auth_headers_a)
    assert len(list_after.json()) == 0


@pytest.mark.asyncio
async def test_uom_duplicate_code_rejected(client: AsyncClient, auth_headers_a):
    create = await client.post("/v1/products", json={"sku": "UOM-DUP-001", "name": "Azúcar", "base_uom": "KG"}, headers=auth_headers_a)
    pid = create.json()["id"]

    payload = {"uom_code": "BULTO", "conversion_factor": 25.0}
    await client.post(f"/v1/products/{pid}/uom", json=payload, headers=auth_headers_a)
    resp = await client.post(f"/v1/products/{pid}/uom", json=payload, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_uom_invalid_conversion_factor(client: AsyncClient, auth_headers_a):
    create = await client.post("/v1/products", json={"sku": "UOM-INV-001", "name": "Test", "base_uom": "UNIT"}, headers=auth_headers_a)
    pid = create.json()["id"]

    resp = await client.post(
        f"/v1/products/{pid}/uom",
        json={"uom_code": "BAD", "conversion_factor": -1},
        headers=auth_headers_a,
    )
    assert resp.status_code == 422
