"""
Tests Sprint 8 — Operaciones Admin: API Keys, Productos, Stock.

Cubre RF-044 (crear API Key desde admin) y RF-045 (portal operativo):
  POST   /admin/tenants/{id}/api-keys
  GET    /admin/tenants/{id}/api-keys
  DELETE /admin/tenants/{id}/api-keys/{key_id}
  GET    /admin/tenants/{id}/products
  POST   /admin/tenants/{id}/products  (incluye sale_price — RN-006-6)
  PATCH  /admin/tenants/{id}/products/{pid}
  DELETE /admin/tenants/{id}/products/{pid}
  GET    /admin/tenants/{id}/categories
  GET    /admin/tenants/{id}/stock
  POST   /admin/tenants/{id}/stock/receipts
  POST   /admin/tenants/{id}/stock/adjustments
  GET    /admin/tenants/{id}/warehouses
  POST   /admin/tenants/{id}/warehouses
  GET    /admin/tenants/{id}/warehouses/{wid}/zones
  POST   /admin/tenants/{id}/warehouses/{wid}/zones
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import _TestSession, uid


# ── Helpers ────────────────────────────────────────────────────────────────

def _product_payload(**overrides) -> dict:
    base = {
        "sku": f"SKU-{uuid.uuid4().hex[:6].upper()}",
        "name": "Producto de Prueba",
        "base_uom": "UND",
    }
    return {**base, **overrides}


async def _setup_warehouse_and_zone(tenant_id: str) -> tuple[str, str]:
    """Crea almacén + zona para el tenant dado. Retorna (warehouse_id, zone_id)."""
    async with _TestSession() as session:
        wid = uid()
        code_suffix = wid[:6]
        await session.execute(
            text(
                "INSERT INTO warehouses (id, tenant_id, code, name, is_virtual, is_active, timezone, created_at, updated_at) "
                "VALUES (:id, :tid, :code, 'Bodega T8', false, true, 'UTC', now(), now())"
            ),
            {"id": wid, "tid": tenant_id, "code": f"WH-{code_suffix}"},
        )
        zid = uid()
        zcode = f"Z-{zid[:6]}"
        await session.execute(
            text(
                "INSERT INTO zones (id, tenant_id, warehouse_id, code, name, zone_type, path, is_active, created_at) "
                "VALUES (:id, :tid, :wid, :code, 'Zona 1', 'GENERAL', :path, true, now())"
            ),
            {"id": zid, "tid": tenant_id, "wid": wid, "code": zcode, "path": zcode},
        )
        await session.commit()
    return wid, zid


async def _get_tenant_for_test() -> str:
    """Crea un tenant temporal y retorna su id. El llamador es responsable de borrarlo."""
    tid = uid()
    slug = f"test-t8-{tid[:8]}"
    async with _TestSession() as session:
        await session.execute(
            text(
                "INSERT INTO tenants (id, name, slug, subscription_tier, config, is_active, created_at, updated_at) "
                "VALUES (:id, 'T8 Tenant', :slug, 'STARTER', '{}', true, now(), now())"
            ),
            {"id": tid, "slug": slug},
        )
        await session.commit()
    return tid


async def _delete_tenant(tenant_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        await session.commit()


# ═══════════════════════════════════════════════════════════════════════════
# RF-044 — Crear / listar / revocar API Keys desde admin
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_create_api_key_success(client: AsyncClient, admin_auth_headers, tenant_a):
    """201: el super_admin crea una API Key para un tenant; secret visible en respuesta."""
    payload = {"name": "Integración Talleres", "scopes": ["READ_INVENTORY", "READ_CATALOG"]}
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        json=payload,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "key_secret" in body, "El secreto debe aparecer en la respuesta de creación"
    assert body["key_secret"].startswith("mk_secret_")
    assert body["name"] == "Integración Talleres"
    assert "READ_INVENTORY" in body["scopes"]
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_admin_create_api_key_secret_not_empty(client: AsyncClient, admin_auth_headers, tenant_a):
    """El key_secret generado no es vacío ni None."""
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        json={"name": "Key de prueba", "scopes": ["ADMIN"]},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()["key_secret"]) > 10


@pytest.mark.asyncio
async def test_admin_create_api_key_requires_super_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """403: tenant_admin no puede crear API Keys desde la superficie admin."""
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        json={"name": "No autorizado", "scopes": ["READ_INVENTORY"]},
        headers=auth_headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_create_api_key_unknown_tenant(client: AsyncClient, admin_auth_headers):
    """404: tenant inexistente."""
    resp = await client.post(
        f"/admin/tenants/{uid()}/api-keys",
        json={"name": "Key para nadie", "scopes": ["READ_INVENTORY"]},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_api_keys(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: listar las API Keys de un tenant; la recién creada aparece."""
    await client.post(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        json={"name": "Key listable", "scopes": ["READ_INVENTORY"]},
        headers=admin_auth_headers,
    )
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    names = [k["name"] for k in body["data"]]
    assert "Key listable" in names


@pytest.mark.asyncio
async def test_admin_revoke_api_key(client: AsyncClient, admin_auth_headers, tenant_a):
    """204: revocar una API Key; después queda is_active=false."""
    create_resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        json={"name": "Para revocar", "scopes": ["READ_INVENTORY"]},
        headers=admin_auth_headers,
    )
    key_id = create_resp.json()["id"]

    revoke_resp = await client.delete(
        f"/admin/tenants/{tenant_a['id']}/api-keys/{key_id}",
        headers=admin_auth_headers,
    )
    assert revoke_resp.status_code == 204

    list_resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/api-keys",
        headers=admin_auth_headers,
        params={"is_active": "false"},
    )
    revoked = [k for k in list_resp.json()["data"] if k["id"] == key_id]
    assert revoked, "La key revocada debe aparecer en la lista con is_active=false"
    assert revoked[0]["is_active"] is False


# ═══════════════════════════════════════════════════════════════════════════
# RF-045 — Admin Productos (admin_products.py)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_list_products_empty(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: tenant sin productos → lista vacía."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/products",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_admin_create_product_success(client: AsyncClient, admin_auth_headers, tenant_a):
    """201: crear producto para un tenant; aparece en listado."""
    payload = _product_payload(name="Filtro de aceite", sale_price=45000.0)
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/products",
        json=payload,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Filtro de aceite"
    assert body["is_active"] is True
    assert float(body["sale_price"]) == 45000.0


@pytest.mark.asyncio
async def test_admin_create_product_without_sale_price(client: AsyncClient, admin_auth_headers, tenant_a):
    """201: sale_price es nullable — se puede omitir."""
    payload = _product_payload(name="Producto sin precio")
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/products",
        json=payload,
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["sale_price"] is None


@pytest.mark.asyncio
async def test_admin_create_product_sku_isolation(client: AsyncClient, admin_auth_headers, tenant_a, tenant_b):
    """Dos tenants pueden tener el mismo SKU sin conflicto (RLS)."""
    sku = f"COMMON-{uuid.uuid4().hex[:6]}"
    for tid in [tenant_a["id"], tenant_b["id"]]:
        resp = await client.post(
            f"/admin/tenants/{tid}/products",
            json=_product_payload(sku=sku, name=f"Prod tenant {tid[:4]}"),
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201, f"Fallo para tenant {tid}: {resp.text}"


@pytest.mark.asyncio
async def test_admin_update_product(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: actualizar nombre y sale_price de un producto."""
    create = await client.post(
        f"/admin/tenants/{tenant_a['id']}/products",
        json=_product_payload(name="Nombre original"),
        headers=admin_auth_headers,
    )
    pid = create.json()["id"]

    resp = await client.patch(
        f"/admin/tenants/{tenant_a['id']}/products/{pid}",
        json={"name": "Nombre actualizado", "sale_price": 99900.0},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Nombre actualizado"
    assert float(resp.json()["sale_price"]) == 99900.0


@pytest.mark.asyncio
async def test_admin_deactivate_product(client: AsyncClient, admin_auth_headers, tenant_a):
    """204: desactivar producto; ya no aparece en listado de activos."""
    create = await client.post(
        f"/admin/tenants/{tenant_a['id']}/products",
        json=_product_payload(name="Para desactivar"),
        headers=admin_auth_headers,
    )
    pid = create.json()["id"]

    del_resp = await client.delete(
        f"/admin/tenants/{tenant_a['id']}/products/{pid}",
        headers=admin_auth_headers,
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/products",
        headers=admin_auth_headers,
    )
    ids = [p["id"] for p in list_resp.json()["data"]]
    assert pid not in ids


@pytest.mark.asyncio
async def test_admin_list_categories(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: listar categorías de un tenant (puede ser lista vacía)."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/categories",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_products_requires_super_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """403: tenant_admin no puede usar los endpoints admin de productos."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/products",
        headers=auth_headers_a,
    )
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# RF-045 — Admin Stock (admin_stock.py)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_stock_balances_empty(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: tenant sin stock → data vacía."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/stock",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_admin_stock_receipt_and_balance(client: AsyncClient, admin_auth_headers, tenant_a):
    """Flujo completo: crear producto → entrada de stock → saldo aparece."""
    tid = tenant_a["id"]

    # Crear producto
    create_p = await client.post(
        f"/admin/tenants/{tid}/products",
        json=_product_payload(name="Producto Stock T8"),
        headers=admin_auth_headers,
    )
    assert create_p.status_code == 201
    product_id = create_p.json()["id"]

    # Crear almacén + zona directamente en DB
    wid, zid = await _setup_warehouse_and_zone(tid)

    # Registrar entrada de stock
    receipt_payload = {
        "reference_type": "PURCHASE_ORDER",
        "reference_id": "PO-T8-001",
        "reason_code": "CARGA_INICIAL",
        "warehouse_id": wid,
        "zone_id": zid,
        "items": [{"product_id": product_id, "quantity": 100, "unit_cost": 5000}],
    }
    receipt_resp = await client.post(
        f"/admin/tenants/{tid}/stock/receipts",
        json=receipt_payload,
        headers=admin_auth_headers,
    )
    assert receipt_resp.status_code == 201, receipt_resp.text

    # Verificar saldo
    stock_resp = await client.get(
        f"/admin/tenants/{tid}/stock",
        headers=admin_auth_headers,
    )
    assert stock_resp.status_code == 200
    balances = stock_resp.json()["data"]
    product_balance = next((b for b in balances if str(b["product_id"]) == product_id), None)
    assert product_balance is not None, "Debe aparecer un saldo para el producto"
    assert float(product_balance["physical_qty"]) == 100.0


@pytest.mark.asyncio
async def test_admin_stock_adjustment(client: AsyncClient, admin_auth_headers, tenant_a):
    """Ajuste de stock: physical_qty cambia al valor new_qty."""
    tid = tenant_a["id"]

    create_p = await client.post(
        f"/admin/tenants/{tid}/products",
        json=_product_payload(name="Producto Ajuste T8"),
        headers=admin_auth_headers,
    )
    product_id = create_p.json()["id"]
    wid, zid = await _setup_warehouse_and_zone(tid)

    # Entrada inicial
    await client.post(
        f"/admin/tenants/{tid}/stock/receipts",
        json={
            "reference_type": "PURCHASE_ORDER",
            "reference_id": "PO-T8-ADJ",
            "reason_code": "CARGA_INICIAL",
            "warehouse_id": wid,
            "zone_id": zid,
            "items": [{"product_id": product_id, "quantity": 50, "unit_cost": 3000}],
        },
        headers=admin_auth_headers,
    )

    # Ajuste a 30
    adj_resp = await client.post(
        f"/admin/tenants/{tid}/stock/adjustments",
        json={
            "reference_id": "AJ-T8-001",
            "reason_code": "CONTEO_FISICO",
            "warehouse_id": wid,
            "zone_id": zid,
            "items": [{"product_id": product_id, "new_qty": 30}],
        },
        headers=admin_auth_headers,
    )
    assert adj_resp.status_code == 201, adj_resp.text

    # Verificar saldo
    stock_resp = await client.get(f"/admin/tenants/{tid}/stock", headers=admin_auth_headers)
    balance = next(
        (b for b in stock_resp.json()["data"] if str(b["product_id"]) == product_id), None
    )
    assert float(balance["physical_qty"]) == 30.0


@pytest.mark.asyncio
async def test_admin_list_warehouses(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: listar almacenes de un tenant (puede ser lista vacía)."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/warehouses",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_list_zones(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: listar zonas de un almacén; devuelve id, name, zone_type."""
    tid = tenant_a["id"]
    wid, zid = await _setup_warehouse_and_zone(tid)

    resp = await client.get(
        f"/admin/tenants/{tid}/warehouses/{wid}/zones",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    zones = resp.json()
    assert any(str(z["id"]) == zid for z in zones)


@pytest.mark.asyncio
async def test_admin_stock_requires_super_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """403: tenant_admin no puede usar los endpoints admin de stock."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/stock",
        headers=auth_headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stock_tenant_isolation(client: AsyncClient, admin_auth_headers, tenant_a, tenant_b):
    """El stock de tenant_a no aparece en el endpoint de tenant_b."""
    tid_a = tenant_a["id"]

    create_p = await client.post(
        f"/admin/tenants/{tid_a}/products",
        json=_product_payload(name="Producto Aislado A"),
        headers=admin_auth_headers,
    )
    product_id = create_p.json()["id"]
    wid, zid = await _setup_warehouse_and_zone(tid_a)

    await client.post(
        f"/admin/tenants/{tid_a}/stock/receipts",
        json={
            "reference_type": "PURCHASE_ORDER",
            "reference_id": "PO-ISO",
            "reason_code": "CARGA_INICIAL",
            "warehouse_id": wid,
            "zone_id": zid,
            "items": [{"product_id": product_id, "quantity": 25, "unit_cost": 1000}],
        },
        headers=admin_auth_headers,
    )

    # Stock del tenant_b debe estar vacío
    resp_b = await client.get(
        f"/admin/tenants/{tenant_b['id']}/stock",
        headers=admin_auth_headers,
    )
    ids_b = [str(b["product_id"]) for b in resp_b.json()["data"]]
    assert product_id not in ids_b, "RLS: el stock de tenant_a no debe aparecer en tenant_b"


@pytest.mark.asyncio
async def test_admin_create_warehouse_autocrea_zonas(client: AsyncClient, admin_auth_headers, tenant_a):
    """201: un almacén físico nace con sus zonas RECEIVING/DISPATCH/QUARANTINE."""
    tid = tenant_a["id"]
    code = f"WH-{uuid.uuid4().hex[:6].upper()}"

    resp = await client.post(
        f"/admin/tenants/{tid}/warehouses",
        json={"code": code, "name": "Bodega Creada Desde Admin", "is_virtual": False},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    wh = resp.json()
    assert wh["code"] == code
    assert wh["is_virtual"] is False

    zonas = await client.get(
        f"/admin/tenants/{tid}/warehouses/{wh['id']}/zones",
        headers=admin_auth_headers,
    )
    tipos = {z["zone_type"] for z in zonas.json()}
    assert {"RECEIVING", "DISPATCH", "QUARANTINE"} <= tipos

    # El almacén recién creado aparece en el listado que consume el portal
    listado = await client.get(f"/admin/tenants/{tid}/warehouses", headers=admin_auth_headers)
    assert any(w["id"] == wh["id"] and w["code"] == code for w in listado.json())


@pytest.mark.asyncio
async def test_admin_create_warehouse_codigo_duplicado(client: AsyncClient, admin_auth_headers, tenant_a):
    """409: el código de almacén es único dentro del tenant."""
    tid = tenant_a["id"]
    payload = {"code": f"WH-{uuid.uuid4().hex[:6].upper()}", "name": "Bodega Repetida"}

    primero = await client.post(
        f"/admin/tenants/{tid}/warehouses", json=payload, headers=admin_auth_headers
    )
    assert primero.status_code == 201

    segundo = await client.post(
        f"/admin/tenants/{tid}/warehouses", json=payload, headers=admin_auth_headers
    )
    assert segundo.status_code == 409


@pytest.mark.asyncio
async def test_admin_create_zone(client: AsyncClient, admin_auth_headers, tenant_a):
    """201: crear una zona adicional en un almacén existente."""
    tid = tenant_a["id"]
    wid, _ = await _setup_warehouse_and_zone(tid)
    zcode = f"ZONA-{uuid.uuid4().hex[:6].upper()}"

    resp = await client.post(
        f"/admin/tenants/{tid}/warehouses/{wid}/zones",
        json={"code": zcode, "name": "Zona de Almacenamiento", "zone_type": "STORAGE"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    zona = resp.json()
    assert zona["code"] == zcode
    assert zona["zone_type"] == "STORAGE"
    assert str(zona["warehouse_id"]) == wid


@pytest.mark.asyncio
async def test_admin_create_warehouse_requires_super_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """403: un tenant_admin no puede crear almacenes por la vía admin."""
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/warehouses",
        json={"code": "WH-NOPE", "name": "No debería crearse"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 403
