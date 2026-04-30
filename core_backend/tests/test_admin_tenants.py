"""
Tests de F-3 — Admin Tenants (RF-037).

Escenarios:
  - Crear tenant: éxito, slug auto-generado, slug explícito en conflicto, email duplicado
  - Listar tenants: paginación básica
  - Obtener tenant: éxito y 404
  - Actualizar tenant: suspensión, reactivación, cambio de tier
  - Acceso sin auth y con rol incorrecto rechazado
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import _TestSession


# ── Helpers ────────────────────────────────────────────────────────────────


async def _delete_tenant(tenant_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        await session.commit()


def _tenant_payload(**overrides) -> dict:
    base = {
        "name": "Acme Corp",
        "subscription_tier": "STARTER",
        "admin_email": "admin@acme.com",
        "admin_full_name": "Acme Admin",
    }
    return {**base, **overrides}


# ── Tests: POST /admin/tenants ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_tenant_success(client: AsyncClient, admin_auth_headers):
    """201: crea tenant + tenant_admin inicial con slug auto-generado."""
    import uuid
    email = f"admin-{uuid.uuid4().hex[:8]}@newcorp.com"
    payload = _tenant_payload(name="New Corp", admin_email=email)
    resp = await client.post("/admin/tenants", json=payload, headers=admin_auth_headers)
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["name"] == "New Corp"
    assert "new-corp" in body["slug"]
    assert body["is_active"] is True
    assert body["subscription_tier"] == "STARTER"
    assert "admin_user_id" in body
    assert body["admin_email"] == email

    await _delete_tenant(body["id"])


@pytest.mark.asyncio
async def test_create_tenant_custom_slug(client: AsyncClient, admin_auth_headers):
    """201: respeta el slug explícito cuando no hay colisión."""
    import uuid
    slug = f"custom-slug-{uuid.uuid4().hex[:6]}"
    email = f"admin-{uuid.uuid4().hex[:8]}@custom.com"
    payload = _tenant_payload(name="Custom Co", slug=slug, admin_email=email)
    resp = await client.post("/admin/tenants", json=payload, headers=admin_auth_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["slug"] == slug

    await _delete_tenant(resp.json()["id"])


@pytest.mark.asyncio
async def test_create_tenant_slug_collision(client: AsyncClient, admin_auth_headers, tenant_a):
    """409: el slug explícito ya está en uso."""
    # Obtener el slug real de tenant_a
    async with _TestSession() as session:
        row = (await session.execute(
            text("SELECT slug FROM tenants WHERE id = :id"), {"id": tenant_a["id"]}
        )).fetchone()
    real_slug = row.slug

    import uuid
    payload = _tenant_payload(
        name="Another Corp",
        slug=real_slug,
        admin_email=f"another-{uuid.uuid4().hex[:8]}@corp.com",
    )
    resp = await client.post("/admin/tenants", json=payload, headers=admin_auth_headers)
    assert resp.status_code == 409
    assert "slug" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_tenant_auto_slug_on_name_collision(client: AsyncClient, admin_auth_headers):
    """Si el slug auto-generado ya existe, se añade sufijo UUID — no falla."""
    import uuid
    email1 = f"admin1-{uuid.uuid4().hex[:8]}@dup.com"
    email2 = f"admin2-{uuid.uuid4().hex[:8]}@dup.com"

    resp1 = await client.post(
        "/admin/tenants",
        json=_tenant_payload(name="Duplicate Name Corp", admin_email=email1),
        headers=admin_auth_headers,
    )
    assert resp1.status_code == 201
    id1 = resp1.json()["id"]

    resp2 = await client.post(
        "/admin/tenants",
        json=_tenant_payload(name="Duplicate Name Corp", admin_email=email2),
        headers=admin_auth_headers,
    )
    assert resp2.status_code == 201
    id2 = resp2.json()["id"]

    assert resp1.json()["slug"] != resp2.json()["slug"]

    await _delete_tenant(id1)
    await _delete_tenant(id2)


@pytest.mark.asyncio
async def test_create_tenant_duplicate_admin_email(client: AsyncClient, admin_auth_headers, user_a):
    """409: el email del tenant_admin ya está registrado en otro tenant."""
    payload = _tenant_payload(
        name="Another Co",
        admin_email=user_a["email"],
    )
    resp = await client.post("/admin/tenants", json=payload, headers=admin_auth_headers)
    assert resp.status_code == 409
    assert "email" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_tenant_invalid_tier(client: AsyncClient, admin_auth_headers):
    """422: tier inválido."""
    import uuid
    payload = _tenant_payload(
        subscription_tier="GOLD",
        admin_email=f"x-{uuid.uuid4().hex[:8]}@x.com",
    )
    resp = await client.post("/admin/tenants", json=payload, headers=admin_auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_requires_auth(client: AsyncClient):
    """401 sin token."""
    resp = await client.post("/admin/tenants", json=_tenant_payload())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_tenant_requires_super_admin(client: AsyncClient, auth_headers_a):
    """403 cuando un tenant_admin intenta crear tenants."""
    import uuid
    payload = _tenant_payload(admin_email=f"x-{uuid.uuid4().hex[:8]}@x.com")
    resp = await client.post("/admin/tenants", json=payload, headers=auth_headers_a)
    assert resp.status_code == 403


# ── Tests: GET /admin/tenants ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tenants_success(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: lista los tenants con paginación."""
    resp = await client.get("/admin/tenants", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1
    assert body["page"] == 1


@pytest.mark.asyncio
async def test_list_tenants_pagination(client: AsyncClient, admin_auth_headers):
    """Los parámetros page y size se respetan."""
    resp = await client.get("/admin/tenants?page=1&size=1", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) <= 1
    assert body["size"] == 1


# ── Tests: GET /admin/tenants/{id} ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tenant_success(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: retorna los datos del tenant."""
    resp = await client.get(f"/admin/tenants/{tenant_a['id']}", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == tenant_a["id"]


@pytest.mark.asyncio
async def test_get_tenant_not_found(client: AsyncClient, admin_auth_headers):
    """404 con un ID inexistente."""
    import uuid
    resp = await client.get(f"/admin/tenants/{uuid.uuid4()}", headers=admin_auth_headers)
    assert resp.status_code == 404


# ── Tests: PATCH /admin/tenants/{id} ─────────────────────────────────────


@pytest.mark.asyncio
async def test_update_tenant_suspend(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: suspender un tenant cambia is_active a False."""
    resp = await client.patch(
        f"/admin/tenants/{tenant_a['id']}",
        json={"is_active": False},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False

    # Restaurar
    await client.patch(
        f"/admin/tenants/{tenant_a['id']}",
        json={"is_active": True},
        headers=admin_auth_headers,
    )


@pytest.mark.asyncio
async def test_update_tenant_change_tier(client: AsyncClient, admin_auth_headers, tenant_a):
    """200: cambia el tier de suscripción."""
    resp = await client.patch(
        f"/admin/tenants/{tenant_a['id']}",
        json={"subscription_tier": "ENTERPRISE"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["subscription_tier"] == "ENTERPRISE"

    # Restaurar
    await client.patch(
        f"/admin/tenants/{tenant_a['id']}",
        json={"subscription_tier": "PROFESSIONAL"},
        headers=admin_auth_headers,
    )


@pytest.mark.asyncio
async def test_update_tenant_not_found(client: AsyncClient, admin_auth_headers):
    """404 al intentar actualizar un tenant inexistente."""
    import uuid
    resp = await client.patch(
        f"/admin/tenants/{uuid.uuid4()}",
        json={"is_active": False},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspended_tenant_user_cannot_login(client: AsyncClient, admin_auth_headers, tenant_a, user_a):
    """Verificar que suspender el tenant bloquea el login de sus usuarios."""
    # Suspender
    await client.patch(
        f"/admin/tenants/{tenant_a['id']}",
        json={"is_active": False},
        headers=admin_auth_headers,
    )

    resp = await client.post(
        "/v1/auth/login",
        json={"email": user_a["email"], "password": "Password123!"},
    )
    assert resp.status_code == 403

    # Restaurar
    await client.patch(
        f"/admin/tenants/{tenant_a['id']}",
        json={"is_active": True},
        headers=admin_auth_headers,
    )
