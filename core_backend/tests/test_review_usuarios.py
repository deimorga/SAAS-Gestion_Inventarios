"""
Revisión 2026-11-19 — R-03 y R-04 (usuarios).

R-03: desactivar a un usuario PENDIENTE no hacía nada (respondía 200 sin cambios ni auditoría) y su
      enlace de activación seguía sirviendo: quien recibiera el email activaba la cuenta. Mismo hueco
      en `update_super_admin`. La activación con el enlace viejo debe responder 410 (no 400: es lo que
      responde `activate_account` para un token que no sirve).
R-04: tras un cambio de rol el usuario conservaba los permisos anteriores hasta 30 min (el rol va en
      el JWT y no se cerraban sus sesiones).
"""
import asyncio
import uuid

import pytest
import redis.asyncio as aioredis
from sqlalchemy import text

from app.core.config import settings
from tests.conftest import _audit_rows, _delete_user_by_id, _insert_user, _TestSession, _user_row


def _email(prefix: str = "rev") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@corp.com"


async def _login(client, email: str, *, admin: bool = False) -> dict:
    path = "/admin/auth/login" if admin else "/v1/auth/login"
    resp = await client.post(path, json={"email": email, "password": "Password123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _token_en_redis(token: str) -> bool:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        return bool(await r.exists(f"activation:{token}"))
    finally:
        await r.aclose()


async def _activate(client, token: str):
    return await client.post("/v1/auth/activate", json={"token": token, "password": "ClaveLarga-2026!"})


# ── R-03: desactivar a un pendiente ────────────────────────────────────────

@pytest.mark.asyncio
async def test_r03_tenant_admin_desactiva_un_pendiente_y_su_enlace_deja_de_servir(client, auth_headers_a, email_spy):
    created = await client.post("/v1/users", json={"email": _email(), "full_name": "Email Equivocado"}, headers=auth_headers_a)
    assert created.status_code == 201, created.text
    uid_ = created.json()["id"]
    token = email_spy.last_token("account_activation", "activation_url")
    try:
        assert await _token_en_redis(token)
        resp = await client.patch(f"/v1/users/{uid_}", json={"is_active": False}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "disabled"
        assert len(await _audit_rows(uid_, "DEACTIVATE")) == 1
        assert not await _token_en_redis(token), "el enlace se borra de Redis al desactivar"

        assert (await _activate(client, token)).status_code == 410
        assert (await _user_row(uid_))["is_active"] is False
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_r03_super_admin_desactiva_un_pendiente_de_un_tenant(client, admin_auth_headers, tenant_a, email_spy):
    created = await client.post(
        f"/admin/tenants/{tenant_a['id']}/users", json={"email": _email(), "full_name": "Pendiente"},
        headers=admin_auth_headers,
    )
    assert created.status_code == 201, created.text
    uid_ = created.json()["id"]
    token = email_spy.last_token("account_activation", "activation_url")
    try:
        resp = await client.patch(
            f"/admin/tenants/{tenant_a['id']}/users/{uid_}", json={"is_active": False}, headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "disabled"
        assert (await _activate(client, token)).status_code == 410

        # Desactivado ya no es pendiente: tampoco se le puede reenviar la activación
        resend = await client.post(
            f"/admin/tenants/{tenant_a['id']}/users/{uid_}/resend-activation", headers=admin_auth_headers
        )
        assert resend.status_code == 409
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_r03_desactivar_un_super_admin_pendiente_invalida_su_enlace(client, admin_auth_headers, email_spy):
    created = await client.post(
        "/admin/super-admins", json={"email": f"sa-test-{uuid.uuid4().hex[:8]}@micronuba.com", "full_name": "SA Pendiente"},
        headers=admin_auth_headers,
    )
    assert created.status_code == 201, created.text
    uid_ = created.json()["id"]
    token = email_spy.last_token("account_activation", "activation_url")
    try:
        resp = await client.patch(f"/admin/super-admins/{uid_}", json={"is_active": False}, headers=admin_auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "disabled"
        assert len(await _audit_rows(uid_, "DEACTIVATE")) == 1
        assert not await _token_en_redis(token)

        assert (await _activate(client, token)).status_code == 410
        assert (await _user_row(uid_))["is_active"] is False
    finally:
        await _delete_user_by_id(uid_)


# ── R-04: cambio de rol ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_r04_bajar_de_rol_a_un_tenant_admin_cierra_su_sesion(client, admin_auth_headers, tenant_a):
    email = _email("admin")
    uid_ = await _insert_user(email, tenant_a["id"], "tenant_admin")
    try:
        old = await _login(client, email)
        assert (await client.get("/v1/users", headers=old)).status_code == 200

        resp = await client.patch(
            f"/admin/tenants/{tenant_a['id']}/users/{uid_}", json={"role": "viewer"}, headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text

        assert (await client.get("/v1/users", headers=old)).status_code == 401, "no conserva los permisos viejos"
        new = await _login(client, email)
        assert (await client.get("/v1/users", headers=new)).status_code == 403, "con el rol nuevo ya no gestiona usuarios"
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_r04_cambiar_el_rol_desde_el_tenant_admin_tambien_cierra_la_sesion(client, auth_headers_a, tenant_a):
    email = _email("viewer")
    uid_ = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        old = await _login(client, email)
        assert (await client.get("/v1/products", headers=old)).status_code == 200

        resp = await client.patch(f"/v1/users/{uid_}", json={"role": "inventory_manager"}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text
        assert (await client.get("/v1/products", headers=old)).status_code == 401
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_r04_cambiar_solo_el_nombre_no_cierra_la_sesion(client, auth_headers_a, tenant_a):
    email = _email("viewer")
    uid_ = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        old = await _login(client, email)
        resp = await client.patch(f"/v1/users/{uid_}", json={"full_name": "Otro Nombre"}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text
        assert (await client.get("/v1/products", headers=old)).status_code == 200
    finally:
        await _delete_user_by_id(uid_)


# ── Ajustes tras la revisión independiente del grupo ───────────────────────

async def _crear_pendiente(client, headers, email_spy, *, nombre: str) -> tuple[str, str]:
    created = await client.post("/v1/users", json={"email": _email(), "full_name": nombre}, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()["id"], email_spy.last_token("account_activation", "activation_url")


@pytest.mark.asyncio
async def test_r03_desactivar_a_un_pendiente_no_toca_el_enlace_de_otro_y_borra_todos_los_suyos(
    client, auth_headers_a, email_spy
):
    """`revoke_activation_tokens` es selectivo: borra TODOS los enlaces del usuario (el reenvío genera uno
    nuevo sin invalidar el anterior) y ninguno de otro."""
    a, token_a1 = await _crear_pendiente(client, auth_headers_a, email_spy, nombre="Pendiente A")
    b, token_b = await _crear_pendiente(client, auth_headers_a, email_spy, nombre="Pendiente B")
    try:
        reenvio = await client.post(f"/v1/auth/resend-activation/{a}", headers=auth_headers_a)
        assert reenvio.status_code in (200, 202, 204), reenvio.text
        token_a2 = email_spy.last_token("activation_resent", "activation_url")
        assert token_a2 != token_a1
        assert await _token_en_redis(token_a1) and await _token_en_redis(token_a2)

        resp = await client.patch(f"/v1/users/{a}", json={"is_active": False}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text

        assert not await _token_en_redis(token_a1)
        assert not await _token_en_redis(token_a2)
        assert await _token_en_redis(token_b), "el enlace de otro pendiente sigue vivo"
        assert (await _activate(client, token_b)).status_code == 200
    finally:
        await _delete_user_by_id(a)
        await _delete_user_by_id(b)


@pytest.mark.asyncio
async def test_r03_solo_se_recorre_redis_al_desactivar_a_un_pendiente(client, auth_headers_a, tenant_a, monkeypatch):
    """Desactivar a un usuario activo no necesita buscar enlaces de activación."""
    llamadas: list[str] = []

    async def espia(user_id, redis):
        llamadas.append(user_id)
        return 0

    monkeypatch.setattr("app.services.user_management.revoke_activation_tokens", espia)
    activo = await _insert_user(_email("activo"), tenant_a["id"], "viewer")
    try:
        resp = await client.patch(f"/v1/users/{activo}", json={"is_active": False}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text
        assert llamadas == []
    finally:
        await _delete_user_by_id(activo)


@pytest.mark.asyncio
async def test_r03_un_pendiente_desactivado_y_reactivado_entra_por_olvide_mi_contrasena(
    client, auth_headers_a, email_spy
):
    """Reactivar a quien se desactivó antes de activarse: no hay enlace que lo lleve a una contraseña, así
    que el camino es «olvidé mi contraseña». Y reactivar no lo deja entrar sin contraseña."""
    uid_, token = await _crear_pendiente(client, auth_headers_a, email_spy, nombre="Pendiente")
    email = (await _user_row(uid_))["email"]
    try:
        assert (await client.patch(f"/v1/users/{uid_}", json={"is_active": False}, headers=auth_headers_a)).status_code == 200
        reactivado = await client.patch(f"/v1/users/{uid_}", json={"is_active": True}, headers=auth_headers_a)
        assert reactivado.status_code == 200, reactivado.text
        assert reactivado.json()["status"] == "active"

        assert (await _activate(client, token)).status_code == 410
        sin_clave = await client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert sin_clave.status_code == 401

        forgot = await client.post("/v1/auth/forgot-password", json={"email": email})
        assert forgot.status_code in (200, 202), forgot.text
        reset_token = email_spy.last_token("password_reset", "reset_url")
        reset = await client.post(
            "/v1/auth/reset-password", json={"token": reset_token, "new_password": "ClaveLarga-2026!"}
        )
        assert reset.status_code == 200, reset.text
        login = await client.post("/v1/auth/login", json={"email": email, "password": "ClaveLarga-2026!"})
        assert login.status_code == 200, login.text
    finally:
        await _delete_user_by_id(uid_)


@pytest.mark.asyncio
async def test_r03_activar_y_desactivar_a_la_vez_deja_al_usuario_desactivado(client, auth_headers_a, email_spy):
    """Carrera: el admin está desactivando (transacción abierta) cuando llega la activación. La activación
    debe esperar y leer el estado nuevo; sin el bloqueo activaba a un usuario recién desactivado."""
    uid_, token = await _crear_pendiente(client, auth_headers_a, email_spy, nombre="Pendiente")
    try:
        async with _TestSession() as admin:
            await admin.execute(
                text("UPDATE users SET is_active = false, must_change_password = false WHERE id = :id"),
                {"id": uid_},
            )  # el admin aún no confirmó
            activacion = asyncio.create_task(_activate(client, token))
            await asyncio.sleep(0.8)
            assert not activacion.done(), "la activación espera a que el admin confirme"
            await admin.commit()
            resp = await asyncio.wait_for(activacion, timeout=10)

        assert resp.status_code == 410, resp.text
        fila = await _user_row(uid_)
        assert fila["is_active"] is False
    finally:
        await _delete_user_by_id(uid_)


# ── R-04: la sesión que se cierra es la completa ───────────────────────────

@pytest.mark.asyncio
async def test_r04_el_refresh_token_anterior_tampoco_sirve_tras_cambiar_el_rol(client, auth_headers_a, tenant_a):
    email = _email("viewer")
    uid_ = await _insert_user(email, tenant_a["id"], "viewer")
    try:
        login = await client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert login.status_code == 200, login.text
        refresh_viejo = login.json()["refresh_token"]

        resp = await client.patch(f"/v1/users/{uid_}", json={"role": "inventory_manager"}, headers=auth_headers_a)
        assert resp.status_code == 200, resp.text

        renovar = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_viejo})
        assert renovar.status_code == 401, "con el refresh token se recuperaría el rol viejo"
    finally:
        await _delete_user_by_id(uid_)
