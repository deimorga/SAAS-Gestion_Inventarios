"""
Revocación inmediata de sesiones (RF-051, HU-USR-002 #3).

Desactivar a un usuario, forzar su reseteo o completar un reseteo cierra TODAS sus sesiones al
momento: el access token deja de valer en el siguiente request y sus refresh tokens se invalidan.
Las API Keys no son sesiones de usuario (RN-051-3) y el cambio voluntario de contraseña no
cierra las demás sesiones (RN-051-2).
"""
import time
import uuid

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient

from app.core.config import settings
from app.services import sessions
from tests.conftest import _delete_user_by_id, _insert_user

CLOSED = "Sesión cerrada. Vuelve a iniciar sesión."


async def _login(client: AsyncClient, email: str, password: str = "Password123!") -> dict:
    resp = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {"access": body["access_token"], "refresh": body["refresh_token"],
            "headers": {"Authorization": f"Bearer {body['access_token']}"}}


async def _admin_patch(client, admin_headers, tenant_id, user_id, payload):
    return await client.patch(f"/admin/tenants/{tenant_id}/users/{user_id}", json=payload, headers=admin_headers)


@pytest.mark.asyncio
async def test_deactivating_a_user_closes_their_session_at_once(client, admin_auth_headers, tenant_a, user_a):
    """El access token vigente da 401 en el siguiente request y el refresh queda inservible."""
    s = await _login(client, user_a["email"])
    assert (await client.get("/v1/users", headers=s["headers"])).status_code == 200

    resp = await _admin_patch(client, admin_auth_headers, tenant_a["id"], user_a["id"], {"is_active": False})
    assert resp.status_code == 200, resp.text

    revoked = await client.get("/v1/users", headers=s["headers"])
    assert revoked.status_code == 401
    assert revoked.json()["detail"] == CLOSED

    refresh = await client.post("/v1/auth/refresh", json={"refresh_token": s["refresh"]})
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_login_right_after_a_revocation_is_not_rejected(client, admin_auth_headers, tenant_a, user_a):
    """Reactivar y volver a entrar en el mismo segundo funciona: el viejo token sigue muerto, el nuevo vale."""
    old = await _login(client, user_a["email"])
    await _admin_patch(client, admin_auth_headers, tenant_a["id"], user_a["id"], {"is_active": False})
    await _admin_patch(client, admin_auth_headers, tenant_a["id"], user_a["id"], {"is_active": True})

    new = await _login(client, user_a["email"])
    assert (await client.get("/v1/users", headers=new["headers"])).status_code == 200
    assert (await client.get("/v1/users", headers=old["headers"])).status_code == 401


@pytest.mark.asyncio
async def test_voluntary_password_change_does_not_close_other_sessions(client, user_a):
    """RN-051-2: el cambio voluntario (RF-040) no cierra las demás sesiones."""
    s = await _login(client, user_a["email"])
    other = await _login(client, user_a["email"])

    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "Password123!", "new_password": "OtraClave-2026!"},
        headers=s["headers"],
    )
    assert resp.status_code == 200, resp.text

    assert (await client.get("/v1/users", headers=other["headers"])).status_code == 200
    refresh = await client.post("/v1/auth/refresh", json={"refresh_token": other["refresh"]})
    assert refresh.status_code == 200


@pytest.mark.asyncio
async def test_api_keys_are_not_affected_by_a_revocation(client, admin_auth_headers, auth_headers_a, tenant_a, user_a):
    """RN-051-3: las API Keys no son sesiones de usuario."""
    created = await client.post(
        "/v1/api-keys", json={"name": f"key-{uuid.uuid4().hex[:6]}", "scopes": ["READ_INVENTORY"]},
        headers=auth_headers_a,
    )
    assert created.status_code == 201, created.text
    secret = created.json()["key_secret"]
    try:
        await _admin_patch(client, admin_auth_headers, tenant_a["id"], user_a["id"], {"is_active": False})
        resp = await client.get("/v1/products", headers={"Authorization": f"Bearer {secret}"})
        assert resp.status_code == 200, resp.text
    finally:
        await client.delete(f"/v1/api-keys/{created.json()['id']}", headers=auth_headers_a)


@pytest.mark.asyncio
async def test_forced_reset_closes_sessions_and_sends_the_email(client, admin_auth_headers, tenant_a, user_a, email_spy):
    s = await _login(client, user_a["email"])

    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/users/{user_a['id']}/password-reset", headers=admin_auth_headers
    )
    assert resp.status_code == 202, resp.text
    assert [c["to_email"] for c in email_spy.of("password_reset")] == [user_a["email"]]

    assert (await client.get("/v1/users", headers=s["headers"])).status_code == 401
    assert (await client.post("/v1/auth/refresh", json={"refresh_token": s["refresh"]})).status_code == 401


@pytest.mark.asyncio
async def test_completing_a_reset_closes_every_session(client, tenant_a, email_spy):
    email = f"sess-{uuid.uuid4().hex[:8]}@corp.com"
    user_id = await _insert_user(email, tenant_a["id"], "tenant_admin")
    try:
        s = await _login(client, email)
        await client.post("/v1/auth/forgot-password", json={"email": email})
        token = email_spy.last_token("password_reset", "reset_url")
        done = await client.post("/v1/auth/reset-password", json={"token": token, "new_password": "OtraClave-2026!"})
        assert done.status_code == 200, done.text

        assert (await client.get("/v1/users", headers=s["headers"])).status_code == 401
        assert (await client.post("/v1/auth/refresh", json={"refresh_token": s["refresh"]})).status_code == 401

        fresh = await _login(client, email, "OtraClave-2026!")
        assert (await client.get("/v1/users", headers=fresh["headers"])).status_code == 200
    finally:
        await _delete_user_by_id(user_id)


# ── Índice de sesiones en Redis ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_index_follows_login_refresh_and_logout(client, user_a):
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        s = await _login(client, user_a["email"])
        assert await r.sismember(sessions.sessions_key(user_a["id"]), s["refresh"])

        refreshed = await client.post("/v1/auth/refresh", json={"refresh_token": s["refresh"]})
        new_refresh = refreshed.json()["refresh_token"]
        assert not await r.sismember(sessions.sessions_key(user_a["id"]), s["refresh"])
        assert await r.sismember(sessions.sessions_key(user_a["id"]), new_refresh)

        await client.post("/v1/auth/logout", json={"refresh_token": new_refresh})
        assert not await r.sismember(sessions.sessions_key(user_a["id"]), new_refresh)
    finally:
        await r.aclose()


@pytest.mark.asyncio
async def test_is_revoked_compares_against_the_revocation_instant():
    """Con `iat_ms` compara al milisegundo; un token sin él se trata como emitido al final de su segundo."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    user_id = str(uuid.uuid4())
    try:
        assert await sessions.is_revoked(user_id, {"iat_ms": 1}, r) is False  # nunca revocado

        await sessions.revoke_all_sessions(user_id, r)
        now_ms = int(time.time() * 1000)

        assert await sessions.is_revoked(user_id, {"iat_ms": now_ms - 5_000}, r) is True
        assert await sessions.is_revoked(user_id, {"iat_ms": now_ms + 5_000}, r) is False
        # Sin iat_ms: emitido antes de la revocación → revocado; en un segundo futuro → vale
        assert await sessions.is_revoked(user_id, {"iat": int(now_ms / 1000) - 5}, r) is True
        assert await sessions.is_revoked(user_id, {"iat": int(now_ms / 1000) + 5}, r) is False
    finally:
        await r.delete(sessions.revoked_key(user_id), sessions.sessions_key(user_id))
        await r.aclose()
