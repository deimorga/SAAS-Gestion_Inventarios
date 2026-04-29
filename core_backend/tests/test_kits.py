"""Tests RF-009 Kits/BOM."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_product(db: AsyncSession, tenant_id: str, sku: str, is_kit: bool = False) -> dict:
    pid = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, :name, 'UNIT', 0, 0, false, false, false, :kit, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": sku, "name": f"Product {sku}", "kit": is_kit},
    )
    await db.commit()
    return {"id": pid, "tenant_id": tenant_id, "sku": sku}


@pytest.mark.asyncio
async def test_add_component_to_kit(client: AsyncClient, auth_headers_a, tenant_a, db):
    kit = await _create_product(db, tenant_a["id"], f"KIT-{uuid.uuid4().hex[:6]}")
    comp = await _create_product(db, tenant_a["id"], f"COMP-{uuid.uuid4().hex[:6]}")
    resp = await client.post(f"/v1/products/{kit['id']}/components", json={
        "component_product_id": comp["id"],
        "quantity": "2.0",
    }, headers=auth_headers_a)
    assert resp.status_code == 201
    data = resp.json()
    assert data["component_product_id"] == comp["id"]
    assert data["quantity"] == "2.0000"


@pytest.mark.asyncio
async def test_list_kit_components(client: AsyncClient, auth_headers_a, tenant_a, db):
    kit = await _create_product(db, tenant_a["id"], f"KITL-{uuid.uuid4().hex[:6]}")
    comp1 = await _create_product(db, tenant_a["id"], f"C1-{uuid.uuid4().hex[:6]}")
    comp2 = await _create_product(db, tenant_a["id"], f"C2-{uuid.uuid4().hex[:6]}")
    await client.post(f"/v1/products/{kit['id']}/components", json={"component_product_id": comp1["id"], "quantity": "1"}, headers=auth_headers_a)
    await client.post(f"/v1/products/{kit['id']}/components", json={"component_product_id": comp2["id"], "quantity": "3"}, headers=auth_headers_a)
    resp = await client.get(f"/v1/products/{kit['id']}/components", headers=auth_headers_a)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_add_duplicate_component_409(client: AsyncClient, auth_headers_a, tenant_a, db):
    kit = await _create_product(db, tenant_a["id"], f"KITDUP-{uuid.uuid4().hex[:6]}")
    comp = await _create_product(db, tenant_a["id"], f"CDUP-{uuid.uuid4().hex[:6]}")
    await client.post(f"/v1/products/{kit['id']}/components", json={"component_product_id": comp["id"], "quantity": "1"}, headers=auth_headers_a)
    resp = await client.post(f"/v1/products/{kit['id']}/components", json={"component_product_id": comp["id"], "quantity": "1"}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_kit_cannot_be_own_component(client: AsyncClient, auth_headers_a, tenant_a, db):
    kit = await _create_product(db, tenant_a["id"], f"SELF-{uuid.uuid4().hex[:6]}")
    resp = await client.post(f"/v1/products/{kit['id']}/components", json={"component_product_id": kit["id"], "quantity": "1"}, headers=auth_headers_a)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nested_kit_rejected(client: AsyncClient, auth_headers_a, tenant_a, db):
    kit1 = await _create_product(db, tenant_a["id"], f"K1-{uuid.uuid4().hex[:6]}", is_kit=True)
    kit2 = await _create_product(db, tenant_a["id"], f"K2-{uuid.uuid4().hex[:6]}")
    # Add comp to kit1 to make it a kit
    comp = await _create_product(db, tenant_a["id"], f"KC-{uuid.uuid4().hex[:6]}")
    await client.post(f"/v1/products/{kit1['id']}/components", json={"component_product_id": comp["id"], "quantity": "1"}, headers=auth_headers_a)
    # Try to use kit1 as component of kit2 — should fail
    resp = await client.post(f"/v1/products/{kit2['id']}/components", json={"component_product_id": kit1["id"], "quantity": "1"}, headers=auth_headers_a)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_remove_kit_component(client: AsyncClient, auth_headers_a, tenant_a, db):
    kit = await _create_product(db, tenant_a["id"], f"KITDEL-{uuid.uuid4().hex[:6]}")
    comp = await _create_product(db, tenant_a["id"], f"CDEL-{uuid.uuid4().hex[:6]}")
    add = await client.post(f"/v1/products/{kit['id']}/components", json={"component_product_id": comp["id"], "quantity": "1"}, headers=auth_headers_a)
    cid = add.json()["id"]
    resp = await client.delete(f"/v1/products/{kit['id']}/components/{cid}", headers=auth_headers_a)
    assert resp.status_code == 204
    # List should be empty
    lst = await client.get(f"/v1/products/{kit['id']}/components", headers=auth_headers_a)
    assert lst.json() == []


@pytest.mark.asyncio
async def test_kit_unauthenticated(client: AsyncClient, tenant_a, db):
    kit = await _create_product(db, tenant_a["id"], f"KITAUTH-{uuid.uuid4().hex[:6]}")
    resp = await client.get(f"/v1/products/{kit['id']}/components")
    assert resp.status_code == 401
