"""
Tests de F-2 — Admin Auth (RF-036).

Cobertura requerida: 100% en módulos auth/admin (DoD Sprint 6).
Escenarios:
  - Bootstrap: deshabilitado, secret incorrecto, éxito, duplicado
  - Admin login: éxito, credenciales incorrectas, separación de superficies
  - Separación inversa: super_admin rechazado en /v1/auth/login
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import settings
from tests.conftest import _TestSession, _delete_user_by_id


# ── Protección de la cuenta raíz (L-1, L-4, T-917) ─────────────────────────
# Antes un fixture autouse borraba TODOS los super_admins de la base antes de cada
# test y los reinsertaba al final. Si el test se cortaba, o si la suite corría contra
# staging, la cuenta raíz se perdía (así pasó el 2026-10-26). Ahora ningún test borra
# ni modifica un super_admin que no creó: cada uno limpia SOLO el id que insertó
# (el fixture `super_admin_user` y el propio test de bootstrap lo hacen por id).


async def _exigir_sin_super_admins() -> None:
    """El bootstrap solo funciona si no existe ningún super_admin.

    Si la base ya tiene uno que este test no creó (la cuenta raíz del ambiente), se
    salta en lugar de borrarlo.
    """
    async with _TestSession() as session:
        existentes = (
            await session.execute(text("SELECT count(*) FROM users WHERE role = 'super_admin'"))
        ).scalar_one()
    if existentes:
        pytest.skip(
            "Hay super_admins que este test no creó (la cuenta raíz del ambiente): "
            "el bootstrap solo se prueba con la base sin ninguno, y no se borra nada ajeno."
        )


# ── Helpers ────────────────────────────────────────────────────────────────


def _unique_email() -> str:
    return f"sa-test-{uuid.uuid4().hex[:8]}@micronuba.com"


# ── Tests: POST /admin/auth/register ──────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_register_bootstrap_disabled(client: AsyncClient, monkeypatch):
    """503 cuando ADMIN_BOOTSTRAP_SECRET no está configurado."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_SECRET", "")
    resp = await client.post(
        "/admin/auth/register",
        json={"email": "sa@micronuba.com", "password": "SuperSecret123!", "full_name": "Admin"},
        headers={"X-Bootstrap-Secret": "anything"},
    )
    assert resp.status_code == 503
    assert "deshabilitado" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_register_wrong_secret(client: AsyncClient, monkeypatch):
    """403 cuando el X-Bootstrap-Secret no coincide."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_SECRET", "correct-secret")
    resp = await client.post(
        "/admin/auth/register",
        json={"email": "sa@micronuba.com", "password": "SuperSecret123!", "full_name": "Admin"},
        headers={"X-Bootstrap-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_register_missing_secret_header(client: AsyncClient, monkeypatch):
    """422 cuando falta el header X-Bootstrap-Secret."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_SECRET", "correct-secret")
    resp = await client.post(
        "/admin/auth/register",
        json={"email": "sa@micronuba.com", "password": "SuperSecret123!", "full_name": "Admin"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_register_success(client: AsyncClient, monkeypatch):
    """201 con token válido al registrar el primer super_admin (solo con la base sin ninguno)."""
    await _exigir_sin_super_admins()
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_SECRET", "test-bootstrap-secret")
    email = _unique_email()
    created_uid: str | None = None

    try:
        resp = await client.post(
            "/admin/auth/register",
            json={"email": email, "password": "SuperSecret123!ABC", "full_name": "Bootstrap Admin"},
            headers={"X-Bootstrap-Secret": "test-bootstrap-secret"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == email
        assert body["user"]["role"] == "super_admin"

        # Recuperar el id para limpieza
        async with _TestSession() as session:
            row = (
                await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": email},
                )
            ).fetchone()
            if row:
                created_uid = str(row.id)
    finally:
        if created_uid:
            await _delete_user_by_id(created_uid)


@pytest.mark.asyncio
async def test_admin_register_duplicate_rejected(client: AsyncClient, super_admin_user, monkeypatch):
    """409 cuando ya existe un super_admin y se intenta registrar otro."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_SECRET", "test-bootstrap-secret")
    resp = await client.post(
        "/admin/auth/register",
        json={"email": _unique_email(), "password": "SuperSecret123!ABC", "full_name": "Admin 2"},
        headers={"X-Bootstrap-Secret": "test-bootstrap-secret"},
    )
    assert resp.status_code == 409
    assert "super_admin" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_register_password_too_short(client: AsyncClient, monkeypatch):
    """422 cuando la contraseña tiene menos de 12 caracteres."""
    monkeypatch.setattr(settings, "ADMIN_BOOTSTRAP_SECRET", "test-bootstrap-secret")
    resp = await client.post(
        "/admin/auth/register",
        json={"email": _unique_email(), "password": "Short1!", "full_name": "Admin"},
        headers={"X-Bootstrap-Secret": "test-bootstrap-secret"},
    )
    assert resp.status_code == 422


# ── Tests: POST /admin/auth/login ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, super_admin_user):
    """200 con JWT de super_admin al autenticar correctamente."""
    resp = await client.post(
        "/admin/auth/login",
        json={"email": super_admin_user["email"], "password": super_admin_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body
    assert body["user"]["role"] == "super_admin"


@pytest.mark.asyncio
async def test_admin_login_wrong_password(client: AsyncClient, super_admin_user):
    """401 con contraseña incorrecta."""
    resp = await client.post(
        "/admin/auth/login",
        json={"email": super_admin_user["email"], "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert "Credenciales" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_login_unknown_email(client: AsyncClient):
    """401 con email inexistente (no revela información)."""
    resp = await client.post(
        "/admin/auth/login",
        json={"email": "nobody@nowhere.com", "password": "SomePassword123!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_rejects_tenant_admin(client: AsyncClient, user_a):
    """403 cuando un tenant_admin intenta usar la superficie /admin/auth/login."""
    resp = await client.post(
        "/admin/auth/login",
        json={"email": user_a["email"], "password": "Password123!"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Acceso denegado"


@pytest.mark.asyncio
async def test_admin_login_inactive_account(client: AsyncClient, super_admin_user):
    """403 cuando la cuenta super_admin está suspendida."""
    async with _TestSession() as session:
        await session.execute(
            text("UPDATE users SET is_active = false WHERE id = :id"),
            {"id": super_admin_user["id"]},
        )
        await session.commit()

    try:
        resp = await client.post(
            "/admin/auth/login",
            json={"email": super_admin_user["email"], "password": super_admin_user["password"]},
        )
        assert resp.status_code == 403
        assert "suspendida" in resp.json()["detail"]
    finally:
        async with _TestSession() as session:
            await session.execute(
                text("UPDATE users SET is_active = true WHERE id = :id"),
                {"id": super_admin_user["id"]},
            )
            await session.commit()


# ── Tests: separación inversa (super_admin rechazado en /v1/auth/login) ───


@pytest.mark.asyncio
async def test_regular_login_rejects_super_admin(client: AsyncClient, super_admin_user):
    """403 cuando super_admin intenta usar la superficie /v1/auth/login."""
    resp = await client.post(
        "/v1/auth/login",
        json={"email": super_admin_user["email"], "password": super_admin_user["password"]},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Acceso denegado"


@pytest.mark.asyncio
async def test_admin_token_is_accepted_on_protected_endpoints(client: AsyncClient, super_admin_user):
    """El JWT de super_admin (emitido por /admin/auth/login) es válido en endpoints protegidos."""
    login = await client.post(
        "/admin/auth/login",
        json={"email": super_admin_user["email"], "password": super_admin_user["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # El health endpoint no requiere auth, pero /v1/audit-logs sí
    resp = await client.get(
        "/v1/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    # super_admin tiene acceso (get_current_auth acepta su JWT)
    assert resp.status_code == 200


# ── Guarda de L-4: ningún test borra usuarios por rol ──────────────────────


def test_ningun_test_borra_ni_modifica_usuarios_por_rol():
    """Regresión del 2026-10-26: un fixture borró todos los super_admins de staging.

    Un test solo puede borrar o modificar el usuario que creó, por su `id`. Filtrar
    por `role` o por `is_protected` toca también cuentas ajenas, la raíz incluida.
    """
    import pathlib
    import re

    # Admite el SQL partido en varias líneas (literales consecutivos).
    prohibido = re.compile(
        r"(DELETE\s+FROM\s+users|UPDATE\s+users\s+SET)[\s\S]{0,200}?WHERE\s+(role|is_protected)\b",
        re.IGNORECASE,
    )
    infractores = []
    for archivo in sorted(pathlib.Path(__file__).parent.glob("test_*.py")):
        if archivo.name == pathlib.Path(__file__).name:
            continue  # este archivo contiene el patrón para poder buscarlo
        texto = archivo.read_text(encoding="utf-8")
        for m in prohibido.finditer(texto):
            n = texto.count("\n", 0, m.start()) + 1
            infractores.append(f"{archivo.name}:{n}")
    assert not infractores, "Borrado o cambio de usuarios por rol en: " + ", ".join(infractores)
