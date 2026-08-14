"""
Entrega del email de activación y reenvío desde el portal de super_admin.

Contexto: el token de activación se generaba y se guardaba en Redis, pero nunca
se encolaba ningún email, y `/v1/auth/resend-activation` rechaza al super_admin
(exige `tenant_admin` del mismo tenant). Resultado: un tenant recién creado
quedaba inaccesible sin tocar la base de datos.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.services import activation as activation_service
from tests.conftest import _TestSession


# ── Helpers ────────────────────────────────────────────────────────────────


class _EmailSpy:
    """Sustituye a send_email.delay y registra las llamadas."""

    def __init__(self, fail: bool = False):
        self.calls: list[dict] = []
        self.fail = fail

    def delay(self, **kwargs):
        if self.fail:
            raise RuntimeError("broker caído")
        self.calls.append(kwargs)


@pytest.fixture
def email_spy(monkeypatch):
    spy = _EmailSpy()
    monkeypatch.setattr("app.tasks.send_email", spy)
    return spy


async def _delete_tenant(tenant_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        await session.commit()


# ── El enlace ──────────────────────────────────────────────────────────────


def test_activation_url_uses_configured_base(monkeypatch):
    monkeypatch.setattr(
        activation_service.settings, "ACTIVATION_BASE_URL", "https://portal.example.com/"
    )
    url = activation_service.activation_url("tok123")
    assert url == "https://portal.example.com/activate?token=tok123"


def test_dispatch_reports_failure_instead_of_raising(monkeypatch):
    """Si el broker falla, se informa con False — no revienta al que llama."""
    monkeypatch.setattr("app.tasks.send_email", _EmailSpy(fail=True))
    ok = activation_service.dispatch_activation_email(
        to_email="x@y.com", full_name="X", token="tok"
    )
    assert ok is False


# ── Alta de tenant ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_tenant_queues_activation_email(
    client: AsyncClient, admin_auth_headers, email_spy
):
    """Crear un tenant debe encolar el email de bienvenida con su enlace."""
    email = f"admin-{uuid.uuid4().hex[:8]}@correo-tenant.com"
    resp = await client.post(
        "/admin/tenants",
        json={
            "name": "Correo Tenant",
            "subscription_tier": "STARTER",
            "admin_email": email,
            "admin_full_name": "Admin Correo",
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    try:
        assert len(email_spy.calls) == 1, "no se encoló el email de activación"
        call = email_spy.calls[0]
        assert call["to_email"] == email
        assert call["template"] == "tenant_created"
        assert "/activate?token=" in call["context"]["activation_url"]
        assert call["context"]["full_name"] == "Admin Correo"
    finally:
        await _delete_tenant(tenant_id)


# ── Reenvío desde el portal de super_admin ─────────────────────────────────


@pytest.mark.asyncio
async def test_admin_can_resend_activation(
    client: AsyncClient, admin_auth_headers, email_spy
):
    """El super_admin puede reenviar la activación de un usuario de otro tenant.

    Es el caso que antes devolvía 403 y dejaba el tenant inaccesible.
    """
    email = f"admin-{uuid.uuid4().hex[:8]}@reenvio.com"
    created = await client.post(
        "/admin/tenants",
        json={
            "name": "Reenvio Corp",
            "subscription_tier": "STARTER",
            "admin_email": email,
            "admin_full_name": "Admin Reenvio",
        },
        headers=admin_auth_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    tenant_id, user_id = body["id"], body["admin_user_id"]
    email_spy.calls.clear()

    try:
        resp = await client.post(
            f"/admin/tenants/{tenant_id}/users/{user_id}/resend-activation",
            headers=admin_auth_headers,
        )
        assert resp.status_code == 200, resp.text

        assert len(email_spy.calls) == 1
        call = email_spy.calls[0]
        assert call["to_email"] == email
        assert call["template"] == "activation_resent"
        assert "/activate?token=" in call["context"]["activation_url"]
    finally:
        await _delete_tenant(tenant_id)


@pytest.mark.asyncio
async def test_admin_list_tenant_users_shows_pending(
    client: AsyncClient, admin_auth_headers, email_spy
):
    """El listado permite identificar quién sigue sin activar."""
    email = f"admin-{uuid.uuid4().hex[:8]}@listado.com"
    created = await client.post(
        "/admin/tenants",
        json={
            "name": "Listado Corp",
            "subscription_tier": "STARTER",
            "admin_email": email,
            "admin_full_name": "Admin Listado",
        },
        headers=admin_auth_headers,
    )
    assert created.status_code == 201, created.text
    tenant_id = created.json()["id"]

    try:
        resp = await client.get(
            f"/admin/tenants/{tenant_id}/users", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == email
        assert items[0]["is_active"] is False
    finally:
        await _delete_tenant(tenant_id)


@pytest.mark.asyncio
async def test_admin_resend_rejects_user_from_another_tenant(
    client: AsyncClient, admin_auth_headers, email_spy, user_a, tenant_b
):
    """Pedir el reenvío con un tenant_id que no es el del usuario da 404."""
    resp = await client.post(
        f"/admin/tenants/{tenant_b['id']}/users/{user_a['id']}/resend-activation",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
    assert email_spy.calls == []


@pytest.mark.asyncio
async def test_admin_resend_conflict_when_already_active(
    client: AsyncClient, admin_auth_headers, email_spy, user_a, tenant_a
):
    """Un usuario ya activo no necesita reenvío: 409."""
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/users/{user_a['id']}/resend-activation",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 409
    assert email_spy.calls == []


@pytest.mark.asyncio
async def test_admin_resend_requires_super_admin(client: AsyncClient, auth_headers_a, user_a, tenant_a):
    """Un tenant_admin no entra por la puerta de admin."""
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/users/{user_a['id']}/resend-activation",
        headers=auth_headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_resend_requires_auth(client: AsyncClient, user_a, tenant_a):
    resp = await client.post(
        f"/admin/tenants/{tenant_a['id']}/users/{user_a['id']}/resend-activation"
    )
    assert resp.status_code == 401
