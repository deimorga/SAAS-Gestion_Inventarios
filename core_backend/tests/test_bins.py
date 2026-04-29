"""Tests RF-014 (Bins/Slots) + RF-015 (Bloqueos de Ubicación)."""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_bin(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"BIN-{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins",
        json={"code": code, "name": "Estante A-1", "max_weight_kg": "500.00"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == code
    assert data["is_active"] is True
    assert data["zone_id"] == zone_a["id"]


@pytest.mark.asyncio
async def test_list_bins(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"LSTBIN-{uuid.uuid4().hex[:6]}"
    await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    resp = await client.get(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", headers=auth_headers_a)
    assert resp.status_code == 200
    assert any(b["code"] == code for b in resp.json())


@pytest.mark.asyncio
async def test_duplicate_bin_code_409(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"DUPBIN-{uuid.uuid4().hex[:6]}"
    await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    resp = await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_bin(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"UPDBIN-{uuid.uuid4().hex[:6]}"
    cr = await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    bid = cr.json()["id"]
    resp = await client.patch(f"/v1/warehouses/bins/{bid}", json={"name": "Nuevo Nombre", "max_weight_kg": "200"}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nuevo Nombre"


@pytest.mark.asyncio
async def test_deactivate_bin(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"DELBIN-{uuid.uuid4().hex[:6]}"
    cr = await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    bid = cr.json()["id"]
    resp = await client.delete(f"/v1/warehouses/bins/{bid}", headers=auth_headers_a)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_bin_invalid_zone(client: AsyncClient, auth_headers_a, warehouse_a):
    resp = await client.post(
        f"/v1/warehouses/{warehouse_a['id']}/zones/{uuid.uuid4()}/bins",
        json={"code": "INVALID"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 404


# ── Location Locks (RF-015) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lock_and_unlock_bin(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"LOCKBIN-{uuid.uuid4().hex[:6]}"
    cr = await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    bid = cr.json()["id"]

    lock_resp = await client.post(f"/v1/warehouses/bins/{bid}/locks", json={"reason": "Mantenimiento programado"}, headers=auth_headers_a)
    assert lock_resp.status_code == 201
    assert lock_resp.json()["is_active"] is True
    assert lock_resp.json()["reason"] == "Mantenimiento programado"

    unlock_resp = await client.delete(f"/v1/warehouses/bins/{bid}/locks", headers=auth_headers_a)
    assert unlock_resp.status_code == 204


@pytest.mark.asyncio
async def test_double_lock_409(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"DLOCK-{uuid.uuid4().hex[:6]}"
    cr = await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    bid = cr.json()["id"]
    await client.post(f"/v1/warehouses/bins/{bid}/locks", json={"reason": "Lock 1"}, headers=auth_headers_a)
    resp = await client.post(f"/v1/warehouses/bins/{bid}/locks", json={"reason": "Lock 2"}, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_unlock_without_lock_404(client: AsyncClient, auth_headers_a, warehouse_a, zone_a):
    code = f"NLOCK-{uuid.uuid4().hex[:6]}"
    cr = await client.post(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins", json={"code": code}, headers=auth_headers_a)
    bid = cr.json()["id"]
    resp = await client.delete(f"/v1/warehouses/bins/{bid}/locks", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bins_unauthenticated(client: AsyncClient, warehouse_a, zone_a):
    resp = await client.get(f"/v1/warehouses/{warehouse_a['id']}/zones/{zone_a['id']}/bins")
    assert resp.status_code == 401
