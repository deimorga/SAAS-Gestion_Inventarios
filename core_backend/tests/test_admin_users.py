"""
Gestión de usuarios de un tenant desde el admin (RF-047, RF-052, HU-USR-002, HU-USR-006).

Escenarios:
  - Listar con estado, filtros por `status` y búsqueda por `q`; los super_admins no aparecen
  - Crear (rol por defecto `viewer`), email único en toda la plataforma, tenant inexistente
  - Editar nombre y rol con auditoría de valores anterior y nuevo; desactivar y reactivar
  - Forzar reseteo y reenviar activación según el estado del usuario
  - Una cuenta protegida no se toca, sea cual sea su rol
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import (
    MICRONUBA_TENANT_ID,
    _audit_rows,
    _delete_user_by_id,
    _insert_user,
    _TestSession,
    _user_row,
)


def _email(prefix: str = "adm") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@corp.com"


def _url(tenant_id: str, suffix: str = "") -> str:
    return f"/admin/tenants/{tenant_id}/users{suffix}"


# ── Listar ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_shows_status_filters_and_hides_super_admins(client, admin_auth_headers, tenant_a):
    tid = tenant_a["id"]
    active = await _insert_user(_email("act"), tid, "viewer")
    pending = await _insert_user(_email("pen"), tid, "viewer", is_active=False, must_change_password=True)
    disabled = await _insert_user(_email("dis"), tid, "viewer", is_active=False, must_change_password=False)
    sa = await _insert_user(f"sa-test-{uuid.uuid4().hex[:8]}@corp.com", tid, "super_admin")
    try:
        resp = await client.get(_url(tid), params={"size": 100}, headers=admin_auth_headers)
        assert resp.status_code == 200
        by_id = {u["id"]: u for u in resp.json()["items"]}
        assert by_id[active]["status"] == "active"
        assert by_id[pending]["status"] == "pending"
        assert by_id[disabled]["status"] == "disabled"
        assert sa not in by_id, "un super_admin no aparece en la gestión de usuarios de un tenant (RN-049-4)"

        only = await client.get(_url(tid), params={"status": "pending"}, headers=admin_auth_headers)
        assert pending in {u["id"] for u in only.json()["items"]}
        assert active not in {u["id"] for u in only.json()["items"]}

        off = await client.get(_url(tid), params={"status": "disabled"}, headers=admin_auth_headers)
        assert {u["id"] for u in off.json()["items"]} == {disabled}

        bad = await client.get(_url(tid), params={"status": "inventado"}, headers=admin_auth_headers)
        assert bad.status_code == 422
    finally:
        for uid_ in (active, pending, disabled, sa):
            await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_list_searches_by_email_or_name(client, admin_auth_headers, tenant_a):
    tid = tenant_a["id"]
    marker = uuid.uuid4().hex[:8]
    mine = await _insert_user(f"buscame-{marker}@corp.com", tid, "viewer", full_name="Persona Única")
    other = await _insert_user(_email("otro"), tid, "viewer", full_name="Otra Persona")
    try:
        by_email = await client.get(_url(tid), params={"q": marker.upper()}, headers=admin_auth_headers)
        assert {u["id"] for u in by_email.json()["items"]} == {mine}

        by_name = await client.get(_url(tid), params={"q": "única"}, headers=admin_auth_headers)
        assert mine in {u["id"] for u in by_name.json()["items"]}
        assert other not in {u["id"] for u in by_name.json()["items"]}

        # `%` y `_` se buscan literalmente: no actúan como comodines
        wild = await client.get(_url(tid), params={"q": "%"}, headers=admin_auth_headers)
        assert wild.json()["total"] == 0
    finally:
        await _delete_user_by_id(mine)
        await _delete_user_by_id(other)


@pytest.mark.asyncio
async def test_internal_tenant_listing_does_not_include_super_admins(client, admin_auth_headers, super_admin_user):
    resp = await client.get(_url(MICRONUBA_TENANT_ID), params={"size": 200}, headers=admin_auth_headers)
    assert resp.status_code == 200
    assert all(u["role"] != "super_admin" for u in resp.json()["items"])


# ── Crear ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_tenant_admin_is_pending_audited_and_emailed(client, admin_auth_headers, tenant_a, email_spy):
    email = _email("nuevo").upper()  # se guarda en minúsculas (RN-052-2)
    resp = await client.post(
        _url(tenant_a["id"]),
        json={"email": email, "full_name": "Ana Admin", "role": "tenant_admin"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    try:
        assert body["email"] == email.lower()
        assert body["role"] == "tenant_admin"
        assert body["status"] == "pending"
        assert body["is_protected"] is False
        assert [c["to_email"] for c in email_spy.of("account_activation")] == [email.lower()]

        rows = await _audit_rows(body["id"], "CREATE")
        assert len(rows) == 1
        assert rows[0]["performed_by"]["role"] == "super_admin"
        assert rows[0]["new_values"] == {"email": email.lower(), "role": "tenant_admin"}
    finally:
        await _delete_user_by_id(body["id"])


@pytest.mark.asyncio
async def test_create_defaults_to_viewer_and_never_creates_super_admins(client, admin_auth_headers, tenant_a):
    ok = await client.post(
        _url(tenant_a["id"]), json={"email": _email(), "full_name": "Sin Rol"}, headers=admin_auth_headers
    )
    assert ok.status_code == 201
    await _delete_user_by_id(ok.json()["id"])
    assert ok.json()["role"] == "viewer"

    bad = await client.post(
        _url(tenant_a["id"]),
        json={"email": _email(), "full_name": "Intruso", "role": "super_admin"},
        headers=admin_auth_headers,
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_create_in_unknown_tenant_is_404(client, admin_auth_headers):
    resp = await client.post(
        _url(str(uuid.uuid4())), json={"email": _email(), "full_name": "Nadie"}, headers=admin_auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_email_is_unique_across_the_whole_platform(client, admin_auth_headers, tenant_a, tenant_b, user_b):
    """409 aunque el email esté en OTRO tenant y se escriba con otras mayúsculas (RN-052-1)."""
    resp = await client.post(
        _url(tenant_a["id"]),
        json={"email": user_b["email"].upper(), "full_name": "Repetido"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "El email ya está registrado"


# ── Editar, desactivar y reactivar ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_name_and_role_is_audited_with_old_and_new_values(client, admin_auth_headers, tenant_a):
    uid_ = await _insert_user(_email(), tenant_a["id"], "viewer", full_name="Nombre Viejo")
    try:
        resp = await client.patch(
            _url(tenant_a["id"], f"/{uid_}"),
            json={"full_name": "Nombre Nuevo", "role": "tenant_admin"},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "tenant_admin"

        (row,) = await _audit_rows(uid_, "UPDATE")
        assert row["old_values"] == {"full_name": "Nombre Viejo", "role": "viewer"}
        assert row["new_values"] == {"full_name": "Nombre Nuevo", "role": "tenant_admin"}
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_deactivate_then_reactivate_is_audited(client, admin_auth_headers, tenant_a):
    uid_ = await _insert_user(_email(), tenant_a["id"], "viewer")
    try:
        off = await client.patch(_url(tenant_a["id"], f"/{uid_}"), json={"is_active": False}, headers=admin_auth_headers)
        assert off.status_code == 200 and off.json()["status"] == "disabled"
        on = await client.patch(_url(tenant_a["id"], f"/{uid_}"), json={"is_active": True}, headers=admin_auth_headers)
        assert on.status_code == 200 and on.json()["status"] == "active"

        assert len(await _audit_rows(uid_, "DEACTIVATE")) == 1
        assert len(await _audit_rows(uid_, "REACTIVATE")) == 1
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_a_pending_user_cannot_be_activated_by_hand(client, admin_auth_headers, tenant_a):
    uid_ = await _insert_user(_email(), tenant_a["id"], "viewer", is_active=False, must_change_password=True)
    try:
        resp = await client.patch(_url(tenant_a["id"], f"/{uid_}"), json={"is_active": True}, headers=admin_auth_headers)
        assert resp.status_code == 409
        assert (await _user_row(uid_))["is_active"] is False
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_user_of_another_tenant_is_404(client, admin_auth_headers, tenant_a, tenant_b):
    uid_ = await _insert_user(_email(), tenant_a["id"], "viewer")
    try:
        resp = await client.patch(_url(tenant_b["id"], f"/{uid_}"), json={"full_name": "Cruzado"}, headers=admin_auth_headers)
        assert resp.status_code == 404
        assert (await _user_row(uid_))["full_name"] != "Cruzado"
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_a_super_admin_cannot_be_managed_through_the_tenant_route(client, admin_auth_headers, tenant_a):
    sa = await _insert_user(f"sa-test-{uuid.uuid4().hex[:8]}@corp.com", tenant_a["id"], "super_admin")
    try:
        resp = await client.patch(_url(tenant_a["id"], f"/{sa}"), json={"is_active": False}, headers=admin_auth_headers)
        assert resp.status_code == 404
        assert (await _user_row(sa))["is_active"] is True
    finally:
        await _delete_user_by_id(sa)


# ── Reseteo forzado y reenvío de activación ────────────────────────────────


@pytest.mark.asyncio
async def test_forced_reset_only_for_active_users(client, admin_auth_headers, tenant_a, email_spy):
    tid = tenant_a["id"]
    active = await _insert_user(_email("a"), tid, "viewer")
    pending = await _insert_user(_email("p"), tid, "viewer", is_active=False, must_change_password=True)
    disabled = await _insert_user(_email("d"), tid, "viewer", is_active=False, must_change_password=False)
    try:
        ok = await client.post(_url(tid, f"/{active}/password-reset"), headers=admin_auth_headers)
        assert ok.status_code == 202
        assert len(email_spy.of("password_reset")) == 1
        (row,) = await _audit_rows(active, "FORCE_PASSWORD_RESET")
        assert row["performed_by"]["role"] == "super_admin"

        for blocked in (pending, disabled):
            resp = await client.post(_url(tid, f"/{blocked}/password-reset"), headers=admin_auth_headers)
            assert resp.status_code == 409
        assert len(email_spy.of("password_reset")) == 1, "a pendientes y desactivados no se les envía nada"
    finally:
        for uid_ in (active, pending, disabled):
            await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_resend_activation_only_for_pending_users(client, admin_auth_headers, tenant_a, email_spy):
    tid = tenant_a["id"]
    pending = await _insert_user(_email("p"), tid, "viewer", is_active=False, must_change_password=True)
    active = await _insert_user(_email("a"), tid, "viewer")
    disabled = await _insert_user(_email("d"), tid, "viewer", is_active=False, must_change_password=False)
    try:
        ok = await client.post(_url(tid, f"/{pending}/resend-activation"), headers=admin_auth_headers)
        assert ok.status_code == 200, ok.text
        assert len(email_spy.of("activation_resent")) == 1
        assert len(await _audit_rows(pending, "RESEND_ACTIVATION")) == 1

        for blocked in (active, disabled):
            resp = await client.post(_url(tid, f"/{blocked}/resend-activation"), headers=admin_auth_headers)
            assert resp.status_code == 409
        assert len(email_spy.of("activation_resent")) == 1
    finally:
        for uid_ in (pending, active, disabled):
            await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_an_old_activation_link_cannot_reactivate_a_disabled_user(client, admin_auth_headers, tenant_a, email_spy):
    """Si lo desactivaron después de enviarle el email, el enlace no lo vuelve a activar."""
    email = _email("tarde")
    created = await client.post(_url(tenant_a["id"]), json={"email": email, "full_name": "Llegó Tarde"}, headers=admin_auth_headers)
    uid_ = created.json()["id"]
    try:
        token = email_spy.last_token("account_activation", "activation_url")
        # Pendiente → desactivarlo exige primero activarlo; se simula el estado «desactivado» por la base
        async with _TestSession() as session:
            await session.execute(text("UPDATE users SET must_change_password = false WHERE id = :id"), {"id": uid_})
            await session.commit()

        resp = await client.post("/v1/auth/activate", json={"token": token, "password": "Clave-Larga-2026!"})
        assert resp.status_code == 410
        assert (await _user_row(uid_))["is_active"] is False
    finally:
        await _delete_user_by_id(uid_)


# ── Cuenta protegida ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_protected_account_cannot_be_touched_whatever_its_role(client, admin_auth_headers, tenant_a):
    """La protección vale para cualquier rol: la cuenta queda intacta (L-1)."""
    uid_ = await _insert_user(f"test-prot-{uuid.uuid4().hex[:8]}@corp.com", tenant_a["id"], "viewer", is_protected=True)
    before = await _user_row(uid_)
    try:
        edit = await client.patch(_url(tenant_a["id"], f"/{uid_}"), json={"full_name": "Cambiado"}, headers=admin_auth_headers)
        off = await client.patch(_url(tenant_a["id"], f"/{uid_}"), json={"is_active": False}, headers=admin_auth_headers)
        role = await client.patch(_url(tenant_a["id"], f"/{uid_}"), json={"role": "tenant_admin"}, headers=admin_auth_headers)
        reset = await client.post(_url(tenant_a["id"], f"/{uid_}/password-reset"), headers=admin_auth_headers)
        resend = await client.post(_url(tenant_a["id"], f"/{uid_}/resend-activation"), headers=admin_auth_headers)

        for resp in (edit, off, role, reset, resend):
            assert resp.status_code == 403, resp.text
            assert resp.json()["detail"] == "Cuenta raíz protegida"
        assert await _user_row(uid_) == before
    finally:
        await _delete_user_by_id(uid_)


# ── Acceso ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_routes_reject_a_tenant_admin(client: AsyncClient, auth_headers_a, tenant_a):
    assert (await client.get(_url(tenant_a["id"]), headers=auth_headers_a)).status_code == 403
    resp = await client.post(_url(tenant_a["id"]), json={"email": _email(), "full_name": "X Y"}, headers=auth_headers_a)
    assert resp.status_code == 403
