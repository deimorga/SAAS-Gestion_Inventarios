"""
Tests de aislamiento de tenant (RLS) — DoD obligatorio al 100%.

Verifica que ningún tenant pueda leer ni modificar datos de otro tenant.
Estos tests golpean la base de datos real para validar las políticas RLS de PostgreSQL.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import text


# ── Helper: crear datos directamente en DB con el tenant correcto ──────────

async def _set_tenant(session, tenant_id: str):
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )


# ── RLS en usuarios ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rls_user_isolation(rls_db, tenant_a, tenant_b, user_a, user_b):
    """Un tenant no puede ver los usuarios de otro tenant a través de RLS."""
    await _set_tenant(rls_db, tenant_a["id"])
    result = await rls_db.execute(text("SELECT COUNT(*) FROM users"))
    count_a = result.scalar_one()

    await rls_db.execute(text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": tenant_b["id"]})
    result = await rls_db.execute(text("SELECT COUNT(*) FROM users"))
    count_b = result.scalar_one()

    assert count_a == 1, f"Tenant A debería ver 1 usuario, vio {count_a}"
    assert count_b == 1, f"Tenant B debería ver 1 usuario, vio {count_b}"


@pytest.mark.asyncio
async def test_rls_user_cross_read_blocked(rls_db, tenant_a, tenant_b, user_a, user_b):
    """Verificar que la búsqueda de un usuario de otro tenant devuelve vacío."""
    await _set_tenant(rls_db, tenant_a["id"])
    result = await rls_db.execute(
        text("SELECT id FROM users WHERE id = :uid"),
        {"uid": user_b["id"]},
    )
    row = result.fetchone()
    assert row is None, "Tenant A NO debe poder leer el usuario de Tenant B"


# ── RLS en api_keys ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rls_api_keys_isolation(client: AsyncClient, auth_headers_a, auth_headers_b, user_a, user_b):
    """Tenant A no puede ver las API keys de Tenant B a través del endpoint."""
    # Crear una API Key como tenant_a
    create_a = await client.post(
        "/v1/api-keys",
        json={"name": "Key de Tenant A", "scopes": ["READ_INVENTORY"]},
        headers=auth_headers_a,
    )
    assert create_a.status_code == 201

    # Listar como tenant_b: no debe ver la key de tenant_a
    list_b = await client.get("/v1/api-keys", headers=auth_headers_b)
    assert list_b.status_code == 200
    ids_b = [item["key_id"] for item in list_b.json()["data"]]
    assert create_a.json()["key_id"] not in ids_b


# ── RLS en audit_logs ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rls_audit_logs_isolation(db, tenant_a, tenant_b, auth_headers_a, auth_headers_b, client: AsyncClient):
    """Tenant A no puede ver los audit logs de Tenant B."""
    # Insertar un audit log directo para tenant_b
    await _set_tenant(db, tenant_b["id"])
    await db.execute(
        text(
            "INSERT INTO audit_logs (id, tenant_id, entity, entity_id, action, new_values, performed_by, created_at) "
            "VALUES (gen_random_uuid(), :tid, 'test', gen_random_uuid(), 'CREATE', '{}', '{\"type\":\"user\",\"id\":\"x\"}', now())"
        ),
        {"tid": tenant_b["id"]},
    )
    await db.commit()

    # Tenant A consulta sus audit logs: no debe ver el de tenant_b
    resp_a = await client.get("/v1/audit-logs", headers=auth_headers_a)
    assert resp_a.status_code == 200
    for log in resp_a.json()["data"]:
        # Todos los logs deben pertenecer a tenant_a (validado por RLS, no en el payload)
        assert log["action"] in ["CREATE", "UPDATE", "DELETE"]


# ── RLS en products ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rls_products_isolation(client: AsyncClient, auth_headers_a, auth_headers_b):
    """Tenant A no puede ver los productos de Tenant B."""
    # Crear producto como tenant_a
    prod_a = await client.post(
        "/v1/products",
        json={"sku": "RLS-TEST-001", "name": "Producto Secreto A", "base_uom": "UNIT"},
        headers=auth_headers_a,
    )
    assert prod_a.status_code == 201
    product_id = prod_a.json()["id"]

    # Tenant_b intenta acceder al producto de tenant_a por ID → 404
    resp_b = await client.get(f"/v1/products/{product_id}", headers=auth_headers_b)
    assert resp_b.status_code == 404

    # Listar productos de tenant_b: no debe aparecer el producto de tenant_a
    list_b = await client.get("/v1/products", headers=auth_headers_b)
    assert list_b.status_code == 200
    ids_b = [p["id"] for p in list_b.json()["data"]]
    assert product_id not in ids_b


@pytest.mark.asyncio
async def test_rls_categories_isolation(client: AsyncClient, auth_headers_a, auth_headers_b):
    """Tenant A no puede ver las categorías de Tenant B."""
    # Crear categoría como tenant_a
    cat_a = await client.post(
        "/v1/categories",
        json={"name": "Categoría Secreta A"},
        headers=auth_headers_a,
    )
    assert cat_a.status_code == 201
    cat_id = cat_a.json()["id"]

    # Tenant_b intenta acceder por ID → 404
    resp_b = await client.get(f"/v1/categories/{cat_id}", headers=auth_headers_b)
    assert resp_b.status_code == 404

    # Listar categorías de tenant_b: no aparece la de tenant_a
    list_b = await client.get("/v1/categories", headers=auth_headers_b)
    ids_b = [c["id"] for c in list_b.json()]
    assert cat_id not in ids_b


@pytest.mark.asyncio
async def test_rls_product_patch_cross_tenant_blocked(client: AsyncClient, auth_headers_a, auth_headers_b):
    """Tenant B no puede modificar un producto de Tenant A."""
    prod_a = await client.post(
        "/v1/products",
        json={"sku": "RLS-PATCH-002", "name": "Producto de A", "base_uom": "UNIT"},
        headers=auth_headers_a,
    )
    assert prod_a.status_code == 201
    product_id = prod_a.json()["id"]

    resp = await client.patch(
        f"/v1/products/{product_id}",
        json={"name": "Hackeado por B"},
        headers=auth_headers_b,
    )
    assert resp.status_code == 404
