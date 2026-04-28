"""Tests de Categorías Jerárquicas (T-108)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_root_category(client: AsyncClient, auth_headers_a):
    resp = await client.post("/v1/categories", json={"name": "Electrónica"}, headers=auth_headers_a)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Electrónica"
    assert body["path"] == "Electrónica"
    assert body["parent_id"] is None
    assert body["slug"] == "electronica"  # slugificado ASCII


@pytest.mark.asyncio
async def test_create_child_category(client: AsyncClient, auth_headers_a):
    parent = await client.post("/v1/categories", json={"name": "Computación"}, headers=auth_headers_a)
    parent_id = parent.json()["id"]

    child = await client.post(
        "/v1/categories",
        json={"name": "Laptops", "parent_id": parent_id},
        headers=auth_headers_a,
    )
    assert child.status_code == 201
    assert child.json()["path"] == "Computación / Laptops"
    assert child.json()["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_category_duplicate_name_same_level(client: AsyncClient, auth_headers_a):
    await client.post("/v1/categories", json={"name": "Hogar"}, headers=auth_headers_a)
    resp = await client.post("/v1/categories", json={"name": "Hogar"}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_category_invalid_parent(client: AsyncClient, auth_headers_a):
    resp = await client.post(
        "/v1/categories",
        json={"name": "Huérfana", "parent_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_categories_tree(client: AsyncClient, auth_headers_a):
    root = await client.post("/v1/categories", json={"name": "Árbol Test"}, headers=auth_headers_a)
    root_id = root.json()["id"]
    await client.post("/v1/categories", json={"name": "Hijo 1", "parent_id": root_id}, headers=auth_headers_a)
    await client.post("/v1/categories", json={"name": "Hijo 2", "parent_id": root_id}, headers=auth_headers_a)

    resp = await client.get("/v1/categories", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    root_node = next((c for c in data if c["id"] == root_id), None)
    assert root_node is not None
    assert len(root_node["children"]) == 2


@pytest.mark.asyncio
async def test_list_categories_flat(client: AsyncClient, auth_headers_a):
    resp = await client.get("/v1/categories?flat=true", headers=auth_headers_a)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_category_detail(client: AsyncClient, auth_headers_a):
    cat = await client.post("/v1/categories", json={"name": "Detalle Test"}, headers=auth_headers_a)
    cat_id = cat.json()["id"]

    resp = await client.get(f"/v1/categories/{cat_id}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == cat_id


@pytest.mark.asyncio
async def test_get_category_not_found(client: AsyncClient, auth_headers_a):
    resp = await client.get("/v1/categories/00000000-0000-0000-0000-000000000000", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_category(client: AsyncClient, auth_headers_a):
    cat = await client.post("/v1/categories", json={"name": "Original Cat"}, headers=auth_headers_a)
    cat_id = cat.json()["id"]

    resp = await client.patch(f"/v1/categories/{cat_id}", json={"name": "Renombrada"}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renombrada"
    assert resp.json()["path"] == "Renombrada"


@pytest.mark.asyncio
async def test_delete_category_empty(client: AsyncClient, auth_headers_a):
    cat = await client.post("/v1/categories", json={"name": "A eliminar"}, headers=auth_headers_a)
    cat_id = cat.json()["id"]

    resp = await client.delete(f"/v1/categories/{cat_id}", headers=auth_headers_a)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_category_with_children_rejected(client: AsyncClient, auth_headers_a):
    parent = await client.post("/v1/categories", json={"name": "Padre con hijos"}, headers=auth_headers_a)
    parent_id = parent.json()["id"]
    await client.post("/v1/categories", json={"name": "Hijo", "parent_id": parent_id}, headers=auth_headers_a)

    resp = await client.delete(f"/v1/categories/{parent_id}", headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_category_with_products_rejected(client: AsyncClient, auth_headers_a):
    cat = await client.post("/v1/categories", json={"name": "Cat con productos"}, headers=auth_headers_a)
    cat_id = cat.json()["id"]

    await client.post(
        "/v1/products",
        json={"sku": "CAT-DEL-001", "name": "Prod en categoría", "base_uom": "UNIT", "category_id": cat_id},
        headers=auth_headers_a,
    )

    resp = await client.delete(f"/v1/categories/{cat_id}", headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_product_filter_by_category_includes_descendants(client: AsyncClient, auth_headers_a):
    """Filtrar por categoría incluye productos de subcategorías."""
    root = await client.post("/v1/categories", json={"name": "Raíz Filter"}, headers=auth_headers_a)
    root_id = root.json()["id"]
    child = await client.post("/v1/categories", json={"name": "Hijo Filter", "parent_id": root_id}, headers=auth_headers_a)
    child_id = child.json()["id"]

    # Producto en la categoría raíz
    await client.post("/v1/products", json={"sku": "ROOT-PROD", "name": "En raíz", "base_uom": "UNIT", "category_id": root_id}, headers=auth_headers_a)
    # Producto en la subcategoría
    await client.post("/v1/products", json={"sku": "CHILD-PROD", "name": "En hijo", "base_uom": "UNIT", "category_id": child_id}, headers=auth_headers_a)

    # Filtrar por root debe devolver ambos
    resp = await client.get(f"/v1/products?category_id={root_id}", headers=auth_headers_a)
    assert resp.status_code == 200
    skus = [p["sku"] for p in resp.json()["data"]]
    assert "ROOT-PROD" in skus
    assert "CHILD-PROD" in skus
