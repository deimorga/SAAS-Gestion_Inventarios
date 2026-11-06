"""
Recuperación de contraseña — «olvidé mi contraseña» (RF-050, RF-052, HU-USR-004).

Escenarios:
  - La respuesta es idéntica exista o no el email (RN-050-1)
  - Pendiente: reenvía la activación; desactivado y tenant suspendido: no envía nada
  - Token de un solo uso; pedir uno nuevo invalida el anterior
  - Límites: 3 por email y hora, 10 por IP y hora
  - Completar el reseteo borra el bloqueo por intentos fallidos de login
  - Política única de 12 caracteres
  - Auditoría sin contraseñas ni tokens
"""
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import _audit_rows, _delete_user_by_id, _insert_user, _TestSession

PUBLIC_MESSAGE = "Si el email está registrado, recibirás un enlace en unos minutos."
NEW_PASSWORD = "NuevaClave-2026!"


def _email(prefix: str = "reset") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@corp.com"


async def _forgot(client: AsyncClient, email: str):
    return await client.post("/v1/auth/forgot-password", json={"email": email})


async def _reset(client: AsyncClient, token: str, password: str = NEW_PASSWORD):
    return await client.post("/v1/auth/reset-password", json={"token": token, "new_password": password})


# ── POST /v1/auth/forgot-password ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_answers_the_same_for_known_and_unknown_email(client, tenant_a, email_spy):
    """202 idéntico exista o no el email: no permite averiguar quién tiene cuenta (RN-050-1)."""
    known = _email()
    user_id = await _insert_user(known, tenant_a["id"], "viewer")
    try:
        a = await _forgot(client, known)
        b = await _forgot(client, _email("nadie"))

        assert a.status_code == b.status_code == 202
        assert a.json() == b.json() == {"message": PUBLIC_MESSAGE}
        # Solo el registrado recibió el email
        assert [c["to_email"] for c in email_spy.of("password_reset")] == [known]
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_forgot_password_is_case_insensitive(client, tenant_a, email_spy):
    email = _email()
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        resp = await _forgot(client, email.upper())
        assert resp.status_code == 202
        assert len(email_spy.of("password_reset")) == 1
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_forgot_password_for_pending_user_resends_activation(client, tenant_a, email_spy):
    """Pendiente: no hay contraseña que recuperar; se reenvía la activación (RN-050-2)."""
    email = _email("pend")
    user_id = await _insert_user(email, tenant_a["id"], "viewer", is_active=False, must_change_password=True)
    try:
        resp = await _forgot(client, email)
        assert resp.status_code == 202
        assert resp.json() == {"message": PUBLIC_MESSAGE}
        assert len(email_spy.of("activation_resent")) == 1
        assert email_spy.of("password_reset") == []
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_forgot_password_sends_nothing_to_disabled_user(client, tenant_a, email_spy):
    """Desactivado: misma respuesta pública y ningún email (RN-050-3)."""
    email = _email("off")
    user_id = await _insert_user(email, tenant_a["id"], "viewer", is_active=False, must_change_password=False)
    try:
        resp = await _forgot(client, email)
        assert resp.status_code == 202
        assert resp.json() == {"message": PUBLIC_MESSAGE}
        assert email_spy.calls == []
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_forgot_password_sends_nothing_when_tenant_is_suspended(client, tenant_a, email_spy):
    email = _email("susp")
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    async with _TestSession() as session:
        await session.execute(text("UPDATE tenants SET is_active = false WHERE id = :id"), {"id": tenant_a["id"]})
        await session.commit()
    try:
        resp = await _forgot(client, email)
        assert resp.status_code == 202
        assert email_spy.calls == []
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_forgot_password_limit_per_email(client, tenant_a, email_spy):
    """429 a la 4.ª solicitud del mismo email en una hora (RN-050-5)."""
    email = _email("lim")
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        for _ in range(3):
            assert (await _forgot(client, email)).status_code == 202
        resp = await _forgot(client, email)
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) > 0
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_forgot_password_limit_per_ip(client, email_spy):
    """429 a la 11.ª solicitud desde la misma IP en una hora, con emails distintos."""
    for _ in range(10):
        assert (await _forgot(client, _email("ip"))).status_code == 202
    assert (await _forgot(client, _email("ip"))).status_code == 429


@pytest.mark.asyncio
async def test_forgot_password_rejects_malformed_email(client):
    assert (await _forgot(client, "no-es-un-email")).status_code == 422


# ── POST /v1/auth/reset-password ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_changes_password_and_token_is_single_use(client, tenant_a, email_spy):
    email = _email()
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        await _forgot(client, email)
        token = email_spy.last_token("password_reset", "reset_url")

        first = await _reset(client, token)
        assert first.status_code == 200, first.text

        again = await _reset(client, token)
        assert again.status_code == 400
        assert again.json()["detail"] == "El enlace no es válido o caducó."

        ok = await client.post("/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})
        old = await client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert ok.status_code == 200
        assert old.status_code == 401
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_second_link_invalidates_the_first(client, tenant_a, email_spy):
    """Solo vale el último token de cada usuario (RN-050-4)."""
    email = _email()
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        await _forgot(client, email)
        await _forgot(client, email)
        tokens = [c["context"]["reset_url"].split("token=")[-1] for c in email_spy.of("password_reset")]
        assert len(tokens) == 2 and tokens[0] != tokens[1]

        assert (await _reset(client, tokens[0])).status_code == 400
        assert (await _reset(client, tokens[1])).status_code == 200
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_reset_password_with_unknown_token(client):
    resp = await _reset(client, "token-que-nunca-existio")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "El enlace no es válido o caducó."


@pytest.mark.asyncio
async def test_reset_password_enforces_12_characters(client, tenant_a, email_spy):
    """422 con menos de 12 caracteres, y el token sigue siendo válido para reintentar."""
    email = _email()
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        await _forgot(client, email)
        token = email_spy.last_token("password_reset", "reset_url")

        assert (await _reset(client, token, "Corta-1234!")).status_code == 422  # 11 caracteres
        assert (await _reset(client, token, "Larga-12345!")).status_code == 200  # 12 caracteres
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_password_policy_is_12_characters_everywhere(client, auth_headers_a):
    """La misma política (RN-052-4) en activación y en cambio voluntario."""
    activate = await client.post("/v1/auth/activate", json={"token": "x", "password": "Corta-1234!"})
    assert activate.status_code == 422

    change = await client.post(
        "/v1/auth/change-password",
        json={"current_password": "Password123!", "new_password": "Corta-1234!"},
        headers=auth_headers_a,
    )
    assert change.status_code == 422


@pytest.mark.asyncio
async def test_completing_a_reset_lifts_the_login_lockout(client, tenant_a, email_spy):
    """Bloqueado por intentos fallidos, al completar el reseteo entra de inmediato (HU-USR-004 #4)."""
    email = _email()
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        for _ in range(5):
            bad = await client.post("/v1/auth/login", json={"email": email, "password": "mala-contraseña-1"})
            assert bad.status_code == 401
        blocked = await client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert blocked.status_code == 429

        await _forgot(client, email)
        assert (await _reset(client, email_spy.last_token("password_reset", "reset_url"))).status_code == 200

        resp = await client.post("/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})
        assert resp.status_code == 200, resp.text
    finally:
        await _delete_user_by_id(user_id)


@pytest.mark.asyncio
async def test_completed_reset_notifies_and_audits_without_secrets(client, tenant_a, email_spy):
    email = _email()
    user_id = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        await _forgot(client, email)
        token = email_spy.last_token("password_reset", "reset_url")
        assert (await _reset(client, token)).status_code == 200

        assert [c["to_email"] for c in email_spy.of("password_changed")] == [email]

        rows = await _audit_rows(user_id, "PASSWORD_RESET")
        assert len(rows) == 1
        assert rows[0]["performed_by"]["id"] == user_id
        blob = json.dumps(rows[0], default=str)
        assert token not in blob and NEW_PASSWORD not in blob and "password_hash" not in blob
    finally:
        await _delete_user_by_id(user_id)
