"""
Tests de autenticación — cobertura 100% de rutas Auth (DoD T-102).
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, user_a):
    resp = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == user_a["email"]
    assert body["user"]["role"] == "tenant_admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user_a):
    resp = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "WrongPass123!"})
    assert resp.status_code == 401
    assert "Credenciales" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post("/v1/auth/login", json={"email": "nobody@nowhere.com", "password": "Password123!"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_body(client: AsyncClient):
    # Contraseña demasiado corta (< 8 chars)
    resp = await client.post("/v1/auth/login", json={"email": "x@x.com", "password": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, user_a):
    login = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["refresh_token"] != refresh_token  # Rotación


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    resp = await client.post("/v1/auth/refresh", json={"refresh_token": "invalid-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_reuse_rejected(client: AsyncClient, user_a):
    """El mismo refresh token no puede usarse dos veces (rotación)."""
    login = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    refresh_token = login.json()["refresh_token"]

    await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    resp2 = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, user_a):
    login = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/v1/auth/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 204

    # Tras logout, el refresh token ya no es válido
    resp2 = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client: AsyncClient):
    resp = await client.get("/v1/audit-logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_invalid_token(client: AsyncClient):
    resp = await client.get("/v1/audit-logs", headers={"Authorization": "Bearer fake.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rate_limit_headers_present(client: AsyncClient, auth_headers_a):
    resp = await client.get("/v1/audit-logs", headers=auth_headers_a)
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


@pytest.mark.asyncio
async def test_login_inactive_user_rejected(client: AsyncClient, db, user_a):
    """Login con cuenta suspendida devuelve 403."""
    await db.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": user_a["id"]})
    await db.commit()

    resp = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    assert resp.status_code == 403

    await db.execute(text("UPDATE users SET is_active = true WHERE id = :id"), {"id": user_a["id"]})
    await db.commit()


@pytest.mark.asyncio
async def test_login_inactive_tenant_rejected(client: AsyncClient, db, user_a, tenant_a):
    """Login con tenant suspendido devuelve 403."""
    await db.execute(text("UPDATE tenants SET is_active = false WHERE id = :id"), {"id": tenant_a["id"]})
    await db.commit()

    resp = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    assert resp.status_code == 403

    await db.execute(text("UPDATE tenants SET is_active = true WHERE id = :id"), {"id": tenant_a["id"]})
    await db.commit()


@pytest.mark.asyncio
async def test_refresh_inactive_user_rejected(client: AsyncClient, db, user_a):
    """Refresh con usuario suspendido tras login devuelve 403."""
    login = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    refresh_token = login.json()["refresh_token"]

    await db.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": user_a["id"]})
    await db.commit()

    resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 403

    await db.execute(text("UPDATE users SET is_active = true WHERE id = :id"), {"id": user_a["id"]})
    await db.commit()


@pytest.mark.asyncio
async def test_refresh_inactive_tenant_rejected(client: AsyncClient, db, user_a, tenant_a):
    """Refresh con tenant suspendido tras login devuelve 403."""
    login = await client.post("/v1/auth/login", json={"email": user_a["email"], "password": "Password123!"})
    refresh_token = login.json()["refresh_token"]

    await db.execute(text("UPDATE tenants SET is_active = false WHERE id = :id"), {"id": tenant_a["id"]})
    await db.commit()

    resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 403

    await db.execute(text("UPDATE tenants SET is_active = true WHERE id = :id"), {"id": tenant_a["id"]})
    await db.commit()
