"""
Gestión de super_admins (RF-049, HU-USR-005) y cuenta raíz protegida (L-1).

Ninguna de estas pruebas toca la cuenta raíz real del ambiente: la protección se verifica con
cuentas `sa-test-*` que crea cada test (`is_protected = true`) y que se borran por su id (L-4).
La regla «siempre queda un super_admin activo» se prueba sustituyendo el bloqueo de filas, porque
con la cuenta raíz activa en la base no se puede llegar a ese estado sin modificarla.
"""
import uuid

import pytest
from httpx import AsyncClient

from app.services import super_admins as service
from tests.conftest import MICRONUBA_TENANT_ID, _audit_rows, _delete_user_by_id, _insert_user, _user_row

URL = "/admin/super-admins"


def _sa_email(prefix: str = "sa-test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@micronuba.com"


async def _admin_login(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/admin/auth/login", json={"email": email, "password": "Password123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Listar y crear ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_shows_status_and_protection(client, admin_auth_headers, super_admin_user):
    resp = await client.get(URL, headers=admin_auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert all(u["role"] == "super_admin" and "is_protected" in u and "status" in u for u in items)
    mine = next(u for u in items if u["id"] == super_admin_user["id"])
    assert mine["is_protected"] is False and mine["status"] == "active"


@pytest.mark.asyncio
async def test_create_super_admin_is_pending_in_the_internal_tenant_and_not_protected(
    client, admin_auth_headers, email_spy
):
    email = _sa_email("nuevo")
    resp = await client.post(URL, json={"email": email.upper(), "full_name": "Segundo Admin"}, headers=admin_auth_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    try:
        assert body["tenant_id"] == MICRONUBA_TENANT_ID
        assert body["email"] == email
        assert body["role"] == "super_admin"
        assert body["status"] == "pending"
        assert body["is_protected"] is False, "proteger otra cuenta no se hace desde la aplicación (RN-049-6)"
        assert [c["to_email"] for c in email_spy.of("account_activation")] == [email]

        (row,) = await _audit_rows(body["id"], "CREATE")
        assert str(row["tenant_id"]) == MICRONUBA_TENANT_ID  # asyncpg devuelve UUID
        assert row["performed_by"]["role"] == "super_admin"
    finally:
        await _delete_user_by_id(body["id"])


@pytest.mark.asyncio
async def test_create_super_admin_with_a_taken_email_is_409(client, admin_auth_headers, super_admin_user, tenant_a):
    other_tenant_user = await _insert_user(f"ocupado-{uuid.uuid4().hex[:8]}@corp.com", tenant_a["id"], "viewer")
    try:
        row = await _user_row(other_tenant_user)
        for taken in (super_admin_user["email"].upper(), row["email"].upper()):
            resp = await client.post(URL, json={"email": taken, "full_name": "Repetido"}, headers=admin_auth_headers)
            assert resp.status_code == 409
    finally:
        await _delete_user_by_id(other_tenant_user)


# ── Desactivar ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_super_admin_cannot_deactivate_themselves(client, admin_auth_headers, super_admin_user):
    resp = await client.patch(f"{URL}/{super_admin_user['id']}", json={"is_active": False}, headers=admin_auth_headers)
    assert resp.status_code == 403
    assert (await _user_row(super_admin_user["id"]))["is_active"] is True


@pytest.mark.asyncio
async def test_deactivating_another_super_admin_closes_their_sessions(client, admin_auth_headers):
    other = await _insert_user(_sa_email(), MICRONUBA_TENANT_ID, "super_admin")
    try:
        other_headers = await _admin_login(client, (await _user_row(other))["email"])
        assert (await client.get(URL, headers=other_headers)).status_code == 200

        off = await client.patch(f"{URL}/{other}", json={"is_active": False}, headers=admin_auth_headers)
        assert off.status_code == 200 and off.json()["status"] == "disabled"
        assert (await client.get(URL, headers=other_headers)).status_code == 401  # RF-051

        on = await client.patch(f"{URL}/{other}", json={"is_active": True}, headers=admin_auth_headers)
        assert on.status_code == 200 and on.json()["status"] == "active"
    finally:
        await _delete_user_by_id(other)


@pytest.mark.asyncio
async def test_a_pending_super_admin_cannot_be_activated_by_hand(client, admin_auth_headers):
    pending = await _insert_user(_sa_email(), MICRONUBA_TENANT_ID, "super_admin", is_active=False, must_change_password=True)
    try:
        resp = await client.patch(f"{URL}/{pending}", json={"is_active": True}, headers=admin_auth_headers)
        assert resp.status_code == 409
    finally:
        await _delete_user_by_id(pending)


@pytest.mark.asyncio
async def test_the_system_always_keeps_one_active_super_admin(client, admin_auth_headers, monkeypatch):
    """409 al desactivar al último activo (RN-049-2)."""
    target = await _insert_user(_sa_email(), MICRONUBA_TENANT_ID, "super_admin")

    async def only_the_target(_db):
        return [target]  # como si, aparte del objetivo, no quedara ningún super_admin activo

    monkeypatch.setattr(service, "_lock_active_super_admin_ids", only_the_target)
    try:
        resp = await client.patch(f"{URL}/{target}", json={"is_active": False}, headers=admin_auth_headers)
        assert resp.status_code == 409
        assert "al menos un super_admin activo" in resp.json()["detail"]
        assert (await _user_row(target))["is_active"] is True
    finally:
        await _delete_user_by_id(target)


@pytest.mark.asyncio
async def test_the_lock_query_sees_every_active_super_admin(db, super_admin_user):
    """El bloqueo de filas devuelve los activos reales (incluida la cuenta raíz, solo lectura)."""
    ids = await service._lock_active_super_admin_ids(db)
    await db.rollback()
    assert super_admin_user["id"] in ids


# ── Cuenta raíz protegida ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_protected_super_admin_cannot_be_deactivated_edited_or_reset(client, admin_auth_headers, email_spy):
    """403 y la cuenta queda intacta, incluida su contraseña (L-1, RN-049-5)."""
    root = await _insert_user(_sa_email("sa-test-raiz"), MICRONUBA_TENANT_ID, "super_admin", is_protected=True)
    before = await _user_row(root)
    try:
        off = await client.patch(f"{URL}/{root}", json={"is_active": False}, headers=admin_auth_headers)
        name = await client.patch(f"{URL}/{root}", json={"full_name": "Otro Nombre"}, headers=admin_auth_headers)
        reset = await client.post(f"{URL}/{root}/password-reset", headers=admin_auth_headers)

        for resp in (off, name, reset):
            assert resp.status_code == 403, resp.text
            assert resp.json()["detail"] == "Cuenta raíz protegida"
        assert await _user_row(root) == before
        assert email_spy.of("password_reset") == [], "no se manda ningún email de reseteo a la cuenta raíz"
        assert await _audit_rows(root, "DEACTIVATE") == []
    finally:
        await _delete_user_by_id(root)


@pytest.mark.asyncio
async def test_the_owner_of_a_protected_account_can_still_recover_their_password(client, email_spy):
    """Solo su dueño cambia su contraseña: «olvidé mi contraseña» sí funciona (RN-049-5, HU-USR-005 #4)."""
    email = _sa_email("sa-test-raiz")
    root = await _insert_user(email, MICRONUBA_TENANT_ID, "super_admin", is_protected=True)
    try:
        assert (await client.post("/v1/auth/forgot-password", json={"email": email})).status_code == 202
        assert [c["to_email"] for c in email_spy.of("password_reset")] == [email]

        token = email_spy.last_token("password_reset", "reset_url")
        done = await client.post("/v1/auth/reset-password", json={"token": token, "new_password": "ClaveNueva-2026!"})
        assert done.status_code == 200, done.text

        login = await client.post("/admin/auth/login", json={"email": email, "password": "ClaveNueva-2026!"})
        assert login.status_code == 200
        assert (await _user_row(root))["is_protected"] is True
    finally:
        await _delete_user_by_id(root)


# ── Reseteo forzado ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forced_reset_of_a_super_admin(client, admin_auth_headers, email_spy):
    active = await _insert_user(_sa_email(), MICRONUBA_TENANT_ID, "super_admin")
    pending = await _insert_user(_sa_email(), MICRONUBA_TENANT_ID, "super_admin", is_active=False, must_change_password=True)
    try:
        ok = await client.post(f"{URL}/{active}/password-reset", headers=admin_auth_headers)
        assert ok.status_code == 202
        assert len(email_spy.of("password_reset")) == 1
        assert len(await _audit_rows(active, "FORCE_PASSWORD_RESET")) == 1

        blocked = await client.post(f"{URL}/{pending}/password-reset", headers=admin_auth_headers)
        assert blocked.status_code == 409
    finally:
        await _delete_user_by_id(active)
        await _delete_user_by_id(pending)


@pytest.mark.asyncio
async def test_unknown_super_admin_is_404(client, admin_auth_headers):
    resp = await client.patch(f"{URL}/{uuid.uuid4()}", json={"full_name": "Nadie Aquí"}, headers=admin_auth_headers)
    assert resp.status_code == 404


# ── Acceso ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_a_super_admin_can_manage_super_admins(client: AsyncClient, auth_headers_a):
    assert (await client.get(URL, headers=auth_headers_a)).status_code == 403
    resp = await client.post(URL, json={"email": _sa_email(), "full_name": "Intruso Total"}, headers=auth_headers_a)
    assert resp.status_code == 403
    assert (await client.get(URL)).status_code == 401
