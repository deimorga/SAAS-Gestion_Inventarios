"""Tests de Almacenes y Zonas — RF-013 (T-201)."""
import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.asyncio
async def test_create_warehouse_success(client: AsyncClient, auth_headers_a):
    resp = await client.post(
        "/v1/warehouses",
        json={"code": "BOG-NTE-01", "name": "Bodega Norte Bogotá", "is_virtual": False},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == "BOG-NTE-01"
    assert body["is_active"] is True
    assert body["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_create_warehouse_auto_zones(client: AsyncClient, auth_headers_a, db):
    resp = await client.post(
        "/v1/warehouses",
        json={"code": "AUTO-ZONES", "name": "Auto Zones Test"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    wh_id = resp.json()["id"]

    # Physical warehouse must auto-create 3 zones
    result = await db.execute(text("SELECT zone_type FROM zones WHERE warehouse_id = :wid ORDER BY zone_type"), {"wid": wh_id})
    zone_types = sorted(r[0] for r in result.fetchall())
    assert "DISPATCH" in zone_types
    assert "QUARANTINE" in zone_types
    assert "RECEIVING" in zone_types


@pytest.mark.asyncio
async def test_create_virtual_warehouse_no_auto_zones(client: AsyncClient, auth_headers_a, db):
    resp = await client.post(
        "/v1/warehouses",
        json={"code": "TRANSIT-01", "name": "Tránsito", "is_virtual": True},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    wh_id = resp.json()["id"]

    result = await db.execute(text("SELECT COUNT(*) FROM zones WHERE warehouse_id = :wid"), {"wid": wh_id})
    assert result.scalar_one() == 0


@pytest.mark.asyncio
async def test_create_warehouse_duplicate_code(client: AsyncClient, auth_headers_a):
    payload = {"code": "DUP-CODE", "name": "Primero"}
    await client.post("/v1/warehouses", json=payload, headers=auth_headers_a)
    resp = await client.post("/v1/warehouses", json={"code": "DUP-CODE", "name": "Segundo"}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_warehouses(client: AsyncClient, auth_headers_a, warehouse_a):
    resp = await client.get("/v1/warehouses", headers=auth_headers_a)
    assert resp.status_code == 200
    codes = [w["code"] for w in resp.json()["data"]]
    assert warehouse_a["code"] in codes


@pytest.mark.asyncio
async def test_get_warehouse_detail(client: AsyncClient, auth_headers_a, warehouse_a):
    resp = await client.get(f"/v1/warehouses/{warehouse_a['id']}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == warehouse_a["id"]


@pytest.mark.asyncio
async def test_get_warehouse_not_found(client: AsyncClient, auth_headers_a):
    resp = await client.get("/v1/warehouses/00000000-0000-0000-0000-000000000000", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_warehouse_name(client: AsyncClient, auth_headers_a, warehouse_a):
    resp = await client.patch(
        f"/v1/warehouses/{warehouse_a['id']}",
        json={"name": "Nombre Actualizado"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nombre Actualizado"


@pytest.mark.asyncio
async def test_warehouse_tenant_isolation(client: AsyncClient, auth_headers_a, warehouse_b):
    """Tenant A no puede ver el almacén del Tenant B."""
    resp = await client.get(f"/v1/warehouses/{warehouse_b['id']}", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_warehouse_invalid_code(client: AsyncClient, auth_headers_a):
    resp = await client.post(
        "/v1/warehouses",
        json={"code": "invalid code!", "name": "Bad"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_zones(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    resp = await client.get(f"/v1/warehouses/{warehouse_a['id']}/zones", headers=auth_headers_a)
    assert resp.status_code == 200
    codes = [z["code"] for z in resp.json()]
    assert zone_a["code"] in codes


@pytest.mark.asyncio
async def test_create_zone_success(client: AsyncClient, auth_headers_a, warehouse_a):
    resp = await client.post(
        f"/v1/warehouses/{warehouse_a['id']}/zones",
        json={"code": "PASILLO-A", "name": "Pasillo A", "zone_type": "STORAGE"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == "PASILLO-A"
    assert body["zone_type"] == "STORAGE"
    assert body["path"] == "PASILLO-A"


@pytest.mark.asyncio
async def test_create_zone_duplicate_code(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    resp = await client.post(
        f"/v1/warehouses/{warehouse_a['id']}/zones",
        json={"code": zone_a["code"], "name": "Dup", "zone_type": "STORAGE"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patch_zone(client: AsyncClient, auth_headers_a, zone_a):
    resp = await client.patch(
        f"/v1/warehouses/zones/{zone_a['id']}",
        json={"zone_type": "QUARANTINE"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    assert resp.json()["zone_type"] == "QUARANTINE"


@pytest.mark.asyncio
async def test_deactivate_warehouse_with_stock_fails(client: AsyncClient, auth_headers_a, warehouse_a, zone_a, product_a, db):
    """RN-013-2: No se puede desactivar un almacén con stock físico > 0."""
    await db.execute(
        text(
            "INSERT INTO stock_balances (id, tenant_id, product_id, warehouse_id, zone_id, "
            "physical_qty, reserved_qty, available_qty, version, updated_at) "
            "VALUES (gen_random_uuid(), :tid, :pid, :wid, :zid, 10, 0, 10, 1, now())"
        ),
        {"tid": warehouse_a["tenant_id"], "pid": product_a["id"], "wid": warehouse_a["id"], "zid": zone_a["id"]},
    )
    await db.commit()

    resp = await client.patch(
        f"/v1/warehouses/{warehouse_a['id']}",
        json={"is_active": False},
        headers=auth_headers_a,
    )
    assert resp.status_code == 409

    # cleanup
    await db.execute(text("DELETE FROM stock_balances WHERE warehouse_id = :wid"), {"wid": warehouse_a["id"]})
    await db.commit()


@pytest.mark.asyncio
async def test_warehouse_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/warehouses")
    assert resp.status_code == 401
