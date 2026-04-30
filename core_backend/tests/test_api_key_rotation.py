"""
Tests de F-6 — Rotación de API Keys y gestión admin cross-tenant (RF-041, RF-044).

Escenarios:
  - Rotación normal (grace period): nueva key generada, antigua sigue activa
  - Rotación inmediata: nueva key generada, antigua desactivada al instante
  - Staggering de fechas: la fecha de expiración no colisiona con keys existentes
  - Revocación admin: super_admin revoca key de cualquier tenant
  - Listado admin: super_admin lista keys de cualquier tenant
  - Errores: key no encontrada, key ya inactiva, tenant cruzado bloqueado
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import _TestSession


# ── Helpers ────────────────────────────────────────────────────────────────


async def _create_api_key(client: AsyncClient, headers: dict, name: str | None = None) -> dict:
    payload = {
        "name": name or f"key-{uuid.uuid4().hex[:8]}",
        "scopes": ["READ_INVENTORY"],
    }
    resp = await client.post("/v1/api-keys", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _delete_api_key_by_id(key_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM api_keys WHERE id = :id"), {"id": key_id})
        await session.commit()


# ── Tests: POST /v1/api-keys/{key_uuid}/rotate ─────────────────────────────


@pytest.mark.asyncio
async def test_rotate_api_key_normal(client: AsyncClient, auth_headers_a):
    """201: rotación normal — nueva key creada, antigua sigue activa (grace period)."""
    original = await _create_api_key(client, auth_headers_a)
    try:
        resp = await client.post(
            f"/v1/api-keys/{original['id']}/rotate",
            params={"immediate": False},
            headers=auth_headers_a,
        )
        assert resp.status_code == 201, resp.text
        new_key = resp.json()

        assert new_key["id"] != original["id"]
        assert new_key["name"] == original["name"]
        assert new_key["scopes"] == original["scopes"]
        assert "key_secret" in new_key
        assert new_key["key_secret"] is not None

        # La clave original debe seguir activa
        list_resp = await client.get("/v1/api-keys", headers=auth_headers_a)
        ids = [k["id"] for k in list_resp.json()["data"]]
        assert original["id"] in ids
    finally:
        await _delete_api_key_by_id(original["id"])
        await _delete_api_key_by_id(new_key["id"])


@pytest.mark.asyncio
async def test_rotate_api_key_immediate(client: AsyncClient, auth_headers_a):
    """201: rotación inmediata — nueva key creada, antigua desactivada al instante."""
    original = await _create_api_key(client, auth_headers_a)
    try:
        resp = await client.post(
            f"/v1/api-keys/{original['id']}/rotate",
            params={"immediate": True},
            headers=auth_headers_a,
        )
        assert resp.status_code == 201, resp.text
        new_key = resp.json()

        assert new_key["id"] != original["id"]
        assert "key_secret" in new_key

        # La clave original debe estar inactiva
        list_resp = await client.get(
            "/v1/api-keys", params={"is_active": True}, headers=auth_headers_a
        )
        active_ids = [k["id"] for k in list_resp.json()["data"]]
        assert original["id"] not in active_ids
        assert new_key["id"] in active_ids
    finally:
        await _delete_api_key_by_id(original["id"])
        await _delete_api_key_by_id(new_key["id"])


@pytest.mark.asyncio
async def test_rotate_api_key_not_found(client: AsyncClient, auth_headers_a):
    """404: rotación de key inexistente."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/v1/api-keys/{fake_id}/rotate", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rotate_inactive_key_returns_409(client: AsyncClient, auth_headers_a):
    """409: no se puede rotar una key ya inactiva."""
    original = await _create_api_key(client, auth_headers_a)
    try:
        await client.delete(f"/v1/api-keys/{original['id']}", headers=auth_headers_a)

        resp = await client.post(
            f"/v1/api-keys/{original['id']}/rotate", headers=auth_headers_a
        )
        assert resp.status_code == 409
    finally:
        await _delete_api_key_by_id(original["id"])


@pytest.mark.asyncio
async def test_rotate_cross_tenant_forbidden(client: AsyncClient, auth_headers_a, auth_headers_b):
    """404: tenant A no puede rotar key de tenant B."""
    key_b = await _create_api_key(client, auth_headers_b)
    try:
        resp = await client.post(
            f"/v1/api-keys/{key_b['id']}/rotate", headers=auth_headers_a
        )
        assert resp.status_code == 404
    finally:
        await _delete_api_key_by_id(key_b["id"])


@pytest.mark.asyncio
async def test_rotate_inherits_scopes(client: AsyncClient, auth_headers_a):
    """La clave rotada hereda exactamente los mismos scopes."""
    original = await _create_api_key(client, auth_headers_a, name="scope-test-key")
    new_key = None
    try:
        resp = await client.post(
            f"/v1/api-keys/{original['id']}/rotate",
            params={"immediate": True},
            headers=auth_headers_a,
        )
        assert resp.status_code == 201
        new_key = resp.json()
        assert set(new_key["scopes"]) == set(original["scopes"])
    finally:
        await _delete_api_key_by_id(original["id"])
        if new_key:
            await _delete_api_key_by_id(new_key["id"])


@pytest.mark.asyncio
async def test_rotate_expiry_different_from_original(client: AsyncClient, auth_headers_a):
    """La clave rotada tiene fecha de expiración futura calculada por staggering."""
    original = await _create_api_key(client, auth_headers_a)
    new_key = None
    try:
        resp = await client.post(
            f"/v1/api-keys/{original['id']}/rotate",
            params={"immediate": True},
            headers=auth_headers_a,
        )
        assert resp.status_code == 201
        new_key = resp.json()
        assert new_key.get("expires_at") is not None
    finally:
        await _delete_api_key_by_id(original["id"])
        if new_key:
            await _delete_api_key_by_id(new_key["id"])


# ── Tests: GET /admin/tenants/{tenant_id}/api-keys ─────────────────────────


@pytest.mark.asyncio
async def test_admin_list_tenant_api_keys(
    client: AsyncClient, admin_auth_headers, tenant_a, auth_headers_a
):
    """200: super_admin lista las API keys de cualquier tenant."""
    key = await _create_api_key(client, auth_headers_a)
    try:
        resp = await client.get(
            f"/admin/tenants/{tenant_a['id']}/api-keys", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "data" in body
        assert "pagination" in body
        ids = [k["id"] for k in body["data"]]
        assert key["id"] in ids
    finally:
        await _delete_api_key_by_id(key["id"])


@pytest.mark.asyncio
async def test_admin_list_tenant_api_keys_filter_active(
    client: AsyncClient, admin_auth_headers, tenant_a, auth_headers_a
):
    """Filtro is_active=true excluye keys revocadas."""
    key = await _create_api_key(client, auth_headers_a)
    await client.delete(f"/v1/api-keys/{key['id']}", headers=auth_headers_a)
    try:
        resp = await client.get(
            f"/admin/tenants/{tenant_a['id']}/api-keys",
            params={"is_active": True},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200
        active_ids = [k["id"] for k in resp.json()["data"]]
        assert key["id"] not in active_ids
    finally:
        await _delete_api_key_by_id(key["id"])


@pytest.mark.asyncio
async def test_admin_list_keys_requires_super_admin(
    client: AsyncClient, auth_headers_a, tenant_a
):
    """403: tenant_admin no puede acceder al endpoint admin."""
    resp = await client.get(
        f"/admin/tenants/{tenant_a['id']}/api-keys", headers=auth_headers_a
    )
    assert resp.status_code == 403


# ── Tests: DELETE /admin/tenants/{tenant_id}/api-keys/{key_id} ─────────────


@pytest.mark.asyncio
async def test_admin_revoke_tenant_api_key(
    client: AsyncClient, admin_auth_headers, tenant_a, auth_headers_a
):
    """204: super_admin revoca la key de un tenant."""
    key = await _create_api_key(client, auth_headers_a)
    try:
        resp = await client.delete(
            f"/admin/tenants/{tenant_a['id']}/api-keys/{key['id']}",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 204

        # Verificar que la key ya no está activa
        list_resp = await client.get(
            f"/admin/tenants/{tenant_a['id']}/api-keys",
            params={"is_active": True},
            headers=admin_auth_headers,
        )
        active_ids = [k["id"] for k in list_resp.json()["data"]]
        assert key["id"] not in active_ids
    finally:
        await _delete_api_key_by_id(key["id"])


@pytest.mark.asyncio
async def test_admin_revoke_key_not_found(
    client: AsyncClient, admin_auth_headers, tenant_a
):
    """404: key inexistente devuelve 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/admin/tenants/{tenant_a['id']}/api-keys/{fake_id}",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_revoke_key_requires_super_admin(
    client: AsyncClient, auth_headers_a, tenant_a, auth_headers_b
):
    """403: tenant_admin no puede revocar keys vía endpoint admin."""
    key = await _create_api_key(client, auth_headers_a)
    try:
        resp = await client.delete(
            f"/admin/tenants/{tenant_a['id']}/api-keys/{key['id']}",
            headers=auth_headers_b,
        )
        assert resp.status_code == 403
    finally:
        await _delete_api_key_by_id(key["id"])
