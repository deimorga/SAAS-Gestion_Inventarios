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

from tests.conftest import _audit_rows, _create_user, _delete_user_by_id, _insert_user, _user_row


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
async def test_create_user_api_consumer_role_is_not_assignable(client: AsyncClient, auth_headers_a):
    """422: `api_consumer` ya no es un rol asignable (RN-052-3): ningún permiso lo reconoce."""
    payload = _user_payload(role="api_consumer")
    resp = await client.post("/v1/users", json=payload, headers=auth_headers_a)
    assert resp.status_code == 422


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
async def test_update_user_suspend(client: AsyncClient, auth_headers_a, tenant_a, db):
    """200: suspende a un colega del tenant y se puede reactivar.

    Antes suspendía al propio tenant_admin que hace la llamada: ahora es 403 (RN-048-3).
    """
    colega = await _create_user(db, tenant_a["id"], f"viewer-{uuid.uuid4().hex[:8]}@alpha.com", role="viewer")
    try:
        resp = await client.patch(
            f"/v1/users/{colega['id']}", json={"is_active": False}, headers=auth_headers_a
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert resp.json()["status"] == "disabled"

        resp = await client.patch(
            f"/v1/users/{colega['id']}", json={"is_active": True}, headers=auth_headers_a
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
    finally:
        await _delete_user_by_id(colega["id"])


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


# ── Módulo 09: reglas del tenant_admin sobre su equipo (RF-048, RF-052) ────


def _plain_email(prefix: str = "team") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@corp.com"


@pytest.mark.asyncio
async def test_create_user_without_role_is_a_pending_viewer_and_is_audited(client: AsyncClient, auth_headers_a, email_spy):
    """RN-048-4: el rol por defecto es `viewer` (antes `api_consumer`, sin permisos)."""
    email = _plain_email()
    resp = await client.post("/v1/users", json={"email": email, "full_name": "Sin Rol"}, headers=auth_headers_a)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    try:
        assert body["role"] == "viewer"
        assert body["status"] == "pending"
        assert [c["to_email"] for c in email_spy.of("account_activation")] == [email]

        (row,) = await _audit_rows(body["id"], "CREATE")
        assert row["performed_by"]["role"] == "tenant_admin"
        assert row["new_values"] == {"email": email, "role": "viewer"}
    finally:
        await _delete_user_by_id(body["id"])


@pytest.mark.asyncio
async def test_tenant_admin_cannot_deactivate_themselves(client: AsyncClient, auth_headers_a, user_a):
    """RN-048-3 (RN-039-4, antes no se cumplía)."""
    resp = await client.patch(f"/v1/users/{user_a['id']}", json={"is_active": False}, headers=auth_headers_a)
    assert resp.status_code == 403
    assert (await _user_row(user_a["id"]))["is_active"] is True


@pytest.mark.asyncio
async def test_tenant_admin_cannot_change_their_own_role(client: AsyncClient, auth_headers_a, user_a):
    """Cambiarse a `viewer` dejaría al tenant sin administrador."""
    resp = await client.patch(f"/v1/users/{user_a['id']}", json={"role": "viewer"}, headers=auth_headers_a)
    assert resp.status_code == 403
    assert (await _user_row(user_a["id"]))["role"] == "tenant_admin"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_manage_another_tenant_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """RN-048-2: ni editar, ni desactivar, ni resetear, ni reenviar la activación."""
    other = await _insert_user(_plain_email("otro-admin"), tenant_a["id"], "tenant_admin")
    before = await _user_row(other)
    try:
        edit = await client.patch(f"/v1/users/{other}", json={"full_name": "Cambiado"}, headers=auth_headers_a)
        off = await client.patch(f"/v1/users/{other}", json={"is_active": False}, headers=auth_headers_a)
        reset = await client.post(f"/v1/users/{other}/password-reset", headers=auth_headers_a)
        resend = await client.post(f"/v1/auth/resend-activation/{other}", headers=auth_headers_a)

        for resp in (edit, off, reset, resend):
            assert resp.status_code == 403, resp.text
        assert await _user_row(other) == before
    finally:
        await _delete_user_by_id(other)


@pytest.mark.asyncio
async def test_tenant_admin_cannot_promote_to_tenant_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """D-04: no se puede escalar privilegios, tampoco con PATCH."""
    colega = await _insert_user(_plain_email(), tenant_a["id"], "viewer")
    try:
        resp = await client.patch(f"/v1/users/{colega}", json={"role": "tenant_admin"}, headers=auth_headers_a)
        assert resp.status_code == 403
        assert (await _user_row(colega))["role"] == "viewer"
    finally:
        await _delete_user_by_id(colega)


@pytest.mark.asyncio
async def test_role_change_is_audited_with_old_and_new_values(client: AsyncClient, auth_headers_a, tenant_a):
    """HU-USR-006: el rol anterior, el nuevo, quién lo hizo y la IP."""
    colega = await _insert_user(_plain_email(), tenant_a["id"], "viewer")
    try:
        resp = await client.patch(f"/v1/users/{colega}", json={"role": "inventory_manager"}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text

        (row,) = await _audit_rows(colega, "UPDATE")
        assert row["old_values"] == {"role": "viewer"}
        assert row["new_values"] == {"role": "inventory_manager"}
        assert row["performed_by"]["role"] == "tenant_admin"
        assert row["ip_address"], "la auditoría guarda la IP"
    finally:
        await _delete_user_by_id(colega)


@pytest.mark.asyncio
async def test_email_taken_in_another_tenant_is_409(client: AsyncClient, auth_headers_a, user_b):
    """RN-052-1: único en toda la plataforma y sin distinguir mayúsculas."""
    resp = await client.post(
        "/v1/users", json={"email": user_b["email"].upper(), "full_name": "Repetido"}, headers=auth_headers_a
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "El email ya está registrado"


@pytest.mark.asyncio
async def test_pending_user_cannot_be_activated_by_hand(client: AsyncClient, auth_headers_a, tenant_a):
    pending = await _insert_user(_plain_email(), tenant_a["id"], "viewer", is_active=False, must_change_password=True)
    try:
        resp = await client.patch(f"/v1/users/{pending}", json={"is_active": True}, headers=auth_headers_a)
        assert resp.status_code == 409
        assert (await _user_row(pending))["is_active"] is False
    finally:
        await _delete_user_by_id(pending)


@pytest.mark.asyncio
async def test_a_protected_user_cannot_be_touched_by_a_tenant_admin(client: AsyncClient, auth_headers_a, tenant_a):
    """La protección vale para cualquier rol, también en la superficie del tenant (L-1)."""
    prot = await _insert_user(_plain_email("test-prot"), tenant_a["id"], "viewer", is_protected=True)
    before = await _user_row(prot)
    try:
        for resp in (
            await client.patch(f"/v1/users/{prot}", json={"full_name": "Cambiado"}, headers=auth_headers_a),
            await client.patch(f"/v1/users/{prot}", json={"is_active": False}, headers=auth_headers_a),
            await client.post(f"/v1/users/{prot}/password-reset", headers=auth_headers_a),
        ):
            assert resp.status_code == 403, resp.text
        assert await _user_row(prot) == before
    finally:
        await _delete_user_by_id(prot)


@pytest.mark.asyncio
async def test_resend_activation_to_a_disabled_user_is_conflict(client: AsyncClient, auth_headers_a, tenant_a, email_spy):
    """Reenviar a un desactivado lo reactivaría por la puerta de atrás: solo se reenvía a pendientes."""
    disabled = await _insert_user(_plain_email(), tenant_a["id"], "viewer", is_active=False, must_change_password=False)
    try:
        resp = await client.post(f"/v1/auth/resend-activation/{disabled}", headers=auth_headers_a)
        assert resp.status_code == 409
        assert email_spy.calls == []
    finally:
        await _delete_user_by_id(disabled)


@pytest.mark.asyncio
async def test_login_is_case_insensitive(client: AsyncClient, user_a):
    """RN-052-2: el email se compara en minúsculas también en el login."""
    resp = await client.post("/v1/auth/login", json={"email": user_a["email"].upper(), "password": "Password123!"})
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_list_filters_by_status_and_search(client: AsyncClient, auth_headers_a, tenant_a):
    marker = uuid.uuid4().hex[:8]
    pending = await _insert_user(f"pend-{marker}@corp.com", tenant_a["id"], "viewer", is_active=False, must_change_password=True)
    disabled = await _insert_user(f"off-{marker}@corp.com", tenant_a["id"], "viewer", is_active=False, must_change_password=False)
    try:
        by_status = await client.get("/v1/users", params={"status": "pending", "q": marker}, headers=auth_headers_a)
        assert {u["id"] for u in by_status.json()["items"]} == {pending}

        by_search = await client.get("/v1/users", params={"q": marker.upper()}, headers=auth_headers_a)
        assert {u["id"] for u in by_search.json()["items"]} == {pending, disabled}

        assert (await client.get("/v1/users", params={"status": "otro"}, headers=auth_headers_a)).status_code == 422
    finally:
        await _delete_user_by_id(pending)
        await _delete_user_by_id(disabled)


@pytest.mark.asyncio
async def test_force_reset_from_the_tenant_surface(client: AsyncClient, auth_headers_a, tenant_a, email_spy):
    colega = await _insert_user(_plain_email(), tenant_a["id"], "viewer")
    try:
        resp = await client.post(f"/v1/users/{colega}/password-reset", headers=auth_headers_a)
        assert resp.status_code == 202, resp.text
        assert len(email_spy.of("password_reset")) == 1
        assert len(await _audit_rows(colega, "FORCE_PASSWORD_RESET")) == 1
    finally:
        await _delete_user_by_id(colega)


@pytest.mark.asyncio
async def test_an_api_key_acting_as_admin_is_audited_as_an_api_key(client: AsyncClient, auth_headers_a, email_spy):
    """Una API Key con scope ADMIN pasa el guard de tenant_admin: la auditoría no la hace pasar por un usuario."""
    key = await client.post(
        "/v1/api-keys", json={"name": f"adm-{uuid.uuid4().hex[:6]}", "scopes": ["ADMIN"]}, headers=auth_headers_a
    )
    assert key.status_code == 201, key.text
    created_id = None
    try:
        resp = await client.post(
            "/v1/users",
            json={"email": _plain_email(), "full_name": "Por API Key"},
            headers={"Authorization": f"Bearer {key.json()['key_secret']}"},
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()["id"]

        (row,) = await _audit_rows(created_id, "CREATE")
        assert row["performed_by"]["type"] == "api_key"
        assert (await _user_row(created_id))["created_by"] is None
    finally:
        if created_id:
            await _delete_user_by_id(created_id)
        await client.delete(f"/v1/api-keys/{key.json()['id']}", headers=auth_headers_a)


@pytest.mark.asyncio
async def test_audit_log_listing_survives_rows_that_carry_an_ip(client: AsyncClient, auth_headers_a):
    """`GET /v1/audit-logs` daba 500 si alguna fila tenía IP: la columna INET llega como IPv4Address.

    Ya pasaba con productos, categorías y almacenes; la gestión de usuarios guarda la IP en todas
    sus acciones, así que cualquier tenant con equipo gestionado lo habría sufrido.
    """
    created = await client.post(
        "/v1/users", json={"email": _plain_email(), "full_name": "Con Auditoría"}, headers=auth_headers_a
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    try:
        resp = await client.get("/v1/audit-logs", params={"entity": "users"}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text
        mine = [e for e in resp.json()["data"] if e["entity_id"] == user_id]
        assert len(mine) == 1
        assert isinstance(mine[0]["ip_address"], str) and mine[0]["ip_address"]
    finally:
        await _delete_user_by_id(user_id)
