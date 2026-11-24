"""
Scopes de las API keys: cada escritura exige su scope (doc/integracion/api_scopes.md).

Antes los scopes se traducían a roles y la key quedaba con el rol más alto que diera cualquiera:
- `READ_INVENTORY` / `READ_CATALOG` daban `inventory_manager` → una key de SOLO LECTURA podía crear
  almacenes, registrar entradas y crear productos;
- `WRITE_CATALOG` también abría las escrituras de inventario, y `MANAGE_RESERVATIONS` las entradas.

Las pruebas solo usan el tenant de la prueba (L-4): sus keys se van con él.
"""
import uuid

import pytest
import pytest_asyncio

from tests.conftest import _create_product_simple, _create_warehouse, _create_zone, uid


@pytest_asyncio.fixture
async def env(db, tenant_a):
    tid = tenant_a["id"]
    wh = await _create_warehouse(db, tid, f"WH-SC-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-SC-{uid()[:6]}")
    product = await _create_product_simple(db, tid, f"SC-{uid()[:6]}")
    return {"wh": wh["id"], "zone": zone["id"], "product": product["id"]}


async def _key(client, auth_headers_a, scopes: list[str]) -> dict:
    resp = await client.post(
        "/v1/api-keys", json={"name": f"scopes-{uuid.uuid4().hex[:6]}", "scopes": scopes}, headers=auth_headers_a
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['key_secret']}"}


def _receipt(env) -> dict:
    return {
        "reference_type": "PURCHASE_ORDER", "reference_id": f"OC-{uid()[:6]}", "reason_code": "COMPRA",
        "warehouse_id": env["wh"], "zone_id": env["zone"],
        "items": [{"product_id": env["product"], "quantity": 5, "unit_cost": 100}],
    }


def _product() -> dict:
    return {"sku": f"SC-NEW-{uid()[:6]}", "name": "Producto por API key", "base_uom": "UNIT"}


def _warehouse() -> dict:
    return {"code": f"WH-K-{uid()[:5]}", "name": "Almacén por API key"}


def _reservation(env) -> dict:
    return {
        "reference_type": "WORK_ORDER", "reference_id": f"OT-{uid()[:6]}",
        "items": [{"product_id": env["product"], "warehouse_id": env["wh"], "zone_id": env["zone"], "quantity": 1}],
    }


@pytest.mark.asyncio
async def test_una_key_de_solo_lectura_lee_pero_no_escribe(client, auth_headers_a, env):
    key = await _key(client, auth_headers_a, ["READ_INVENTORY", "READ_CATALOG"])

    assert (await client.get("/v1/stock/balances", headers=key)).status_code == 200
    assert (await client.get("/v1/products", headers=key)).status_code == 200
    assert (await client.get("/v1/warehouses", headers=key)).status_code == 200

    assert (await client.post("/v1/warehouses", json=_warehouse(), headers=key)).status_code == 403
    assert (await client.post("/v1/transactions/receipts", json=_receipt(env), headers=key)).status_code == 403
    assert (await client.post("/v1/products", json=_product(), headers=key)).status_code == 403
    assert (await client.post("/v1/reservations", json=_reservation(env), headers=key)).status_code == 403


@pytest.mark.asyncio
async def test_write_catalog_no_abre_las_escrituras_de_inventario(client, auth_headers_a, env):
    key = await _key(client, auth_headers_a, ["READ_CATALOG", "WRITE_CATALOG"])

    assert (await client.post("/v1/products", json=_product(), headers=key)).status_code == 201
    assert (await client.post("/v1/transactions/receipts", json=_receipt(env), headers=key)).status_code == 403
    assert (await client.post("/v1/warehouses", json=_warehouse(), headers=key)).status_code == 403


@pytest.mark.asyncio
async def test_write_inventory_no_abre_las_escrituras_de_catalogo(client, auth_headers_a, env):
    key = await _key(client, auth_headers_a, ["READ_INVENTORY", "WRITE_INVENTORY"])

    assert (await client.post("/v1/transactions/receipts", json=_receipt(env), headers=key)).status_code == 201
    assert (await client.post("/v1/products", json=_product(), headers=key)).status_code == 403


@pytest.mark.asyncio
async def test_manage_reservations_reserva_pero_no_registra_entradas(client, auth_headers_a, env):
    key = await _key(client, auth_headers_a, ["READ_INVENTORY", "MANAGE_RESERVATIONS"])

    assert (await client.post("/v1/transactions/receipts", json=_receipt(env), headers=key)).status_code == 403
    # Sin stock la reserva da 409, pero pasa el control de permisos
    assert (await client.post("/v1/reservations", json=_reservation(env), headers=key)).status_code != 403


@pytest.mark.asyncio
async def test_manage_warehouses_crea_almacenes_pero_no_mueve_stock(client, auth_headers_a, env):
    key = await _key(client, auth_headers_a, ["READ_INVENTORY", "MANAGE_WAREHOUSES"])

    assert (await client.post("/v1/warehouses", json=_warehouse(), headers=key)).status_code == 201
    assert (await client.post("/v1/transactions/receipts", json=_receipt(env), headers=key)).status_code == 403


@pytest.mark.asyncio
async def test_la_key_de_una_sede_con_todos_los_scopes_sigue_pudiendo_todo(client, auth_headers_a, env):
    """La que aprovisiona `/v1/platform/tenants` para Appits: no debe perder nada."""
    key = await _key(client, auth_headers_a, [
        "READ_CATALOG", "WRITE_CATALOG", "READ_INVENTORY", "WRITE_INVENTORY", "MANAGE_WAREHOUSES", "MANAGE_RESERVATIONS",
    ])

    assert (await client.post("/v1/products", json=_product(), headers=key)).status_code == 201
    assert (await client.post("/v1/warehouses", json=_warehouse(), headers=key)).status_code == 201
    assert (await client.post("/v1/transactions/receipts", json=_receipt(env), headers=key)).status_code == 201
    assert (await client.post("/v1/reservations", json=_reservation(env), headers=key)).status_code == 201
