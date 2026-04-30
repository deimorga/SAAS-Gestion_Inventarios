"""
Tests de F-4 — Activación de cuenta (RF-038, RF-040).

Escenarios:
  - Activar cuenta: éxito, token single-use, token expirado (410), contraseña débil
  - Resend activación: éxito, cuenta ya activa, tenant incorrecto
  - Cambiar contraseña (RF-040): éxito, contraseña actual incorrecta
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import (
    _TestSession,
    _delete_user_by_id,
)
from app.core.redis_client import get_redis
from app.services.activation import generate_activation_token


# ── Helpers ────────────────────────────────────────────────────────────────


async def _create_inactive_user(tenant_id: str, email: str) -> str:
    """Crea usuario inactivo que espera activación."""
    uid_ = str(uuid.uuid4())
    async with _TestSession() as session:
        await session.execute(
            text(
                "INSERT INTO users "
                "(id, tenant_id, email, password_hash, full_name, role, "
                " is_active, must_change_password, created_at) "
                "VALUES (:id, :tid, :email, 'placeholder', 'Test User', 'tenant_admin', "
                "        false, true, now())"
            ),
            {"id": uid_, "tid": tenant_id, "email": email},
        )
        await session.commit()
    return uid_


async def _get_redis_client():
    async for r in get_redis():
        return r


# ── Tests: POST /v1/auth/activate ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_success(client: AsyncClient, tenant_a):
    """200: activa la cuenta, permite login después."""
    email = f"inactive-{uuid.uuid4().hex[:8]}@tenant.com"
    uid_ = await _create_inactive_user(tenant_a["id"], email)

    redis = await _get_redis_client()
    token = await generate_activation_token(uid_, redis)

    try:
        resp = await client.post(
            "/v1/auth/activate",
            json={"token": token, "password": "NewPassword123!"},
        )
        assert resp.status_code == 200, resp.text
        assert "activada" in resp.json()["message"]

        # El usuario ahora puede autenticarse
        login = await client.post(
            "/v1/auth/login",
            json={"email": email, "password": "NewPassword123!"},
        )
        assert login.status_code == 200
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_activate_token_single_use(client: AsyncClient, tenant_a):
    """410 en el segundo intento con el mismo token."""
    email = f"su-{uuid.uuid4().hex[:8]}@tenant.com"
    uid_ = await _create_inactive_user(tenant_a["id"], email)

    redis = await _get_redis_client()
    token = await generate_activation_token(uid_, redis)

    try:
        r1 = await client.post(
            "/v1/auth/activate",
            json={"token": token, "password": "FirstPass123!"},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            "/v1/auth/activate",
            json={"token": token, "password": "SecondPass123!"},
        )
        assert r2.status_code == 410
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_activate_invalid_token(client: AsyncClient):
    """410 con token inexistente."""
    resp = await client.post(
        "/v1/auth/activate",
        json={"token": "token-invalido-que-no-existe", "password": "SomePass123!"},
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_activate_password_too_short(client: AsyncClient, tenant_a):
    """422 cuando la nueva contraseña tiene menos de 8 caracteres."""
    email = f"pwshort-{uuid.uuid4().hex[:8]}@tenant.com"
    uid_ = await _create_inactive_user(tenant_a["id"], email)

    redis = await _get_redis_client()
    token = await generate_activation_token(uid_, redis)

    try:
        resp = await client.post(
            "/v1/auth/activate",
            json={"token": token, "password": "short"},
        )
        assert resp.status_code == 422
        # Token no fue consumido (falló validación antes de llegar al service)
        r2 = await client.post(
            "/v1/auth/activate",
            json={"token": token, "password": "ValidPass123!"},
        )
        assert r2.status_code == 200
    finally:
        await _delete_user_by_id(uid_)


# ── Tests: POST /v1/auth/resend-activation/{user_id} ──────────────────────


@pytest.mark.asyncio
async def test_resend_activation_success(client: AsyncClient, auth_headers_a, tenant_a):
    """200: tenant_admin puede reenviar activación a un usuario de su tenant."""
    email = f"resend-{uuid.uuid4().hex[:8]}@tenant.com"
    uid_ = await _create_inactive_user(tenant_a["id"], email)

    try:
        resp = await client.post(
            f"/v1/auth/resend-activation/{uid_}",
            headers=auth_headers_a,
        )
        assert resp.status_code == 200, resp.text
        assert "regenerado" in resp.json()["message"]
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_resend_activation_already_active(client: AsyncClient, auth_headers_a, user_a):
    """409 cuando la cuenta ya está activa y no tiene must_change_password."""
    resp = await client.post(
        f"/v1/auth/resend-activation/{user_a['id']}",
        headers=auth_headers_a,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_resend_activation_wrong_tenant(client: AsyncClient, auth_headers_a, tenant_b, user_b):
    """404 cuando el usuario no pertenece al tenant del solicitante."""
    resp = await client.post(
        f"/v1/auth/resend-activation/{user_b['id']}",
        headers=auth_headers_a,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_resend_activation_requires_tenant_admin(client: AsyncClient, tenant_a):
    """401 sin token de autenticación."""
    email = f"noauth-{uuid.uuid4().hex[:8]}@tenant.com"
    uid_ = await _create_inactive_user(tenant_a["id"], email)
    try:
        resp = await client.post(f"/v1/auth/resend-activation/{uid_}")
        assert resp.status_code == 401
    finally:
        await _delete_user_by_id(uid_)


# ── Tests: POST /v1/auth/change-password (RF-040) ─────────────────────────


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, user_a):
    """200: el usuario puede cambiar su contraseña con la actual correcta."""
    # Login para obtener token
    login = await client.post(
        "/v1/auth/login",
        json={"email": user_a["email"], "password": "Password123!"},
    )
    token = login.json()["access_token"]

    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "Password123!", "new_password": "NewPassword456!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    # Verificar que la nueva contraseña funciona
    login2 = await client.post(
        "/v1/auth/login",
        json={"email": user_a["email"], "password": "NewPassword456!"},
    )
    assert login2.status_code == 200

    # Restaurar contraseña original
    token2 = login2.json()["access_token"]
    await client.post(
        "/v1/auth/change-password",
        json={"current_password": "NewPassword456!", "new_password": "Password123!"},
        headers={"Authorization": f"Bearer {token2}"},
    )


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, auth_headers_a):
    """401 cuando la contraseña actual es incorrecta."""
    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "WrongCurrent!", "new_password": "NewPassword456!"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_auth(client: AsyncClient):
    """401 sin token."""
    resp = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "Password123!", "new_password": "NewPassword456!"},
    )
    assert resp.status_code == 401
