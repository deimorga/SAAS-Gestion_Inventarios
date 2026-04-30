"""
Tests de F-5 — Gestión de Usuarios por tenant_admin (RF-039).

Escenarios:
  - Crear usuario: éxito, rol no permitido (tenant_admin), email duplicado
  - Listar usuarios: paginación, aislamiento RLS
  - Actualizar usuario: nombre, suspensión
  - Acceso denegado: rol incorrecto, tenant cruzado
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import _delete_user_by_id


# ── Helpers ────────────────────────────────────────────────────────────────


def _user_payload(**overrides) -> dict:
    base = {
        "email": f"user-{uuid.uuid4().hex[:8]}@corp.com",
        "full_name": "Test User",
        "role": "inventory_manager",
    }
    return {**base, **overrides}


# ── Tests: POST /v1/users ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_user_success(client: AsyncClient, auth_headers_a):
    """201: tenant_admin crea un usuario con rol permitido."""
    payload = _user_payload(role="inventory_manager")
    resp = await client.post("/v1/users", json=payload, headers=auth_headers_a)
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["email"] == payload["email"]
    assert body["role"] == "inventory_manager"
    assert body["is_active"] is False
    assert body["must_change_password"] is True

    await _delete_user_by_id(body["id"])


@pytest.mark.asyncio
async def test_create_user_viewer_role(client: AsyncClient, auth_headers_a):
    """201: tenant_admin puede crear viewer."""
    payload = _user_payload(role="viewer")
    resp = await client.post("/v1/users", json=payload, headers=auth_headers_a)
    assert resp.status_code == 201
    await _delete_user_by_id(resp.json()["id"])


@pytest.mark.asyncio
async def test_create_user_api_consumer_role(client: AsyncClient, auth_headers_a):
    """201: tenant_admin puede crear api_consumer."""
    payload = _user_payload(role="api_consumer")
    resp = await client.post("/v1/users", json=payload, headers=auth_headers_a)
    assert resp.status_code == 201
    await _delete_user_by_id(resp.json()["id"])


@pytest.mark.asyncio
async def test_create_user_tenant_admin_role_forbidden(client: AsyncClient, auth_headers_a):
    """403: tenant_admin no puede crear otro tenant_admin (escalada de privilegios)."""
    payload = _user_payload(role="tenant_admin")
    resp = await client.post("/v1/users", json=payload, headers=auth_headers_a)
    assert resp.status_code == 403
    assert "tenant_admin" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient, auth_headers_a, user_a):
    """409: email ya registrado en el tenant."""
    payload = _user_payload(email=user_a["email"])
    resp = await client.post("/v1/users", json=payload, headers=auth_headers_a)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_requires_tenant_admin(client: AsyncClient, auth_headers_a, tenant_a, db):
    """403 cuando un inventory_manager intenta crear usuarios."""
    # Crear un inventory_manager y autenticarse como él
    uid_ = str(uuid.uuid4())
    email = f"mgr-{uuid.uuid4().hex[:8]}@corp.com"
    from app.core.security import hash_password
    await db.execute(
        text(
            "INSERT INTO users (id, tenant_id, email, password_hash, full_name, role, is_active, created_at) "
            "VALUES (:id, :tid, :email, :pw, 'Manager', 'inventory_manager', true, now())"
        ),
        {"id": uid_, "tid": tenant_a["id"], "email": email, "pw": hash_password("Password123!")},
    )
    await db.commit()

    login = await client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
    mgr_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    try:
        resp = await client.post("/v1/users", json=_user_payload(), headers=mgr_headers)
        assert resp.status_code == 403
    finally:
        await _delete_user_by_id(uid_)


# ── Tests: GET /v1/users ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_success(client: AsyncClient, auth_headers_a, user_a):
    """200: lista usuarios del tenant."""
    resp = await client.get("/v1/users", headers=auth_headers_a)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert body["total"] >= 1
    user_ids = [u["id"] for u in body["items"]]
    assert user_a["id"] in user_ids


@pytest.mark.asyncio
async def test_list_users_rls_isolation(client: AsyncClient, auth_headers_a, user_b):
    """Tenant A no puede ver usuarios de Tenant B."""
    resp = await client.get("/v1/users", headers=auth_headers_a)
    assert resp.status_code == 200
    user_ids = [u["id"] for u in resp.json()["items"]]
    assert user_b["id"] not in user_ids


@pytest.mark.asyncio
async def test_list_users_pagination(client: AsyncClient, auth_headers_a):
    """Los parámetros page y size se respetan."""
    resp = await client.get("/v1/users?page=1&size=1", headers=auth_headers_a)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 1


# ── Tests: PATCH /v1/users/{user_id} ─────────────────────────────────────


@pytest.mark.asyncio
async def test_update_user_name(client: AsyncClient, auth_headers_a, user_a):
    """200: actualiza el nombre del usuario."""
    resp = await client.patch(
        f"/v1/users/{user_a['id']}",
        json={"full_name": "Nombre Actualizado"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["full_name"] == "Nombre Actualizado"

    # Restaurar
    await client.patch(
        f"/v1/users/{user_a['id']}",
        json={"full_name": "Test User"},
        headers=auth_headers_a,
    )


@pytest.mark.asyncio
async def test_update_user_suspend(client: AsyncClient, auth_headers_a, user_a):
    """200: suspende al usuario."""
    resp = await client.patch(
        f"/v1/users/{user_a['id']}",
        json={"is_active": False},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Restaurar
    await client.patch(
        f"/v1/users/{user_a['id']}",
        json={"is_active": True},
        headers=auth_headers_a,
    )


@pytest.mark.asyncio
async def test_update_user_cross_tenant_forbidden(client: AsyncClient, auth_headers_a, user_b):
    """404 al intentar modificar un usuario de otro tenant."""
    resp = await client.patch(
        f"/v1/users/{user_b['id']}",
        json={"full_name": "Hackeado"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_not_found(client: AsyncClient, auth_headers_a):
    """404 con ID inexistente."""
    resp = await client.patch(
        f"/v1/users/{uuid.uuid4()}",
        json={"full_name": "Nadie"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 404
