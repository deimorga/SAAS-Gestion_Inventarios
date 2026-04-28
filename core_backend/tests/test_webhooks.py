"""Tests para el módulo de Webhooks (Sprint 4: T-401 y T-402)."""
import hashlib
import hmac
import json

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.services.webhook import dispatch_event, sign_payload
from tests.conftest import _TestSession, uid


# ── Helpers ────────────────────────────────────────────────────────────────────

_VALID_BODY = {
    "url": "https://example.com/hooks/inventory",
    "secret": "mi-secreto-seguro-minimo-16chars",
    "events": ["transaction.receipt", "reservation.created"],
}


async def _create_webhook(client, headers, body=None):
    return await client.post("/v1/webhooks", json=body or _VALID_BODY, headers=headers)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def webhook_setup(client, auth_headers_a):
    resp = await _create_webhook(client, auth_headers_a)
    assert resp.status_code == 201, resp.text
    yield resp.json()


# ── T-401: CRUD endpoints ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_webhook_success(client, auth_headers_a):
    resp = await _create_webhook(client, auth_headers_a)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["url"] == _VALID_BODY["url"]
    assert data["events"] == _VALID_BODY["events"]
    assert data["is_active"] is True
    assert "secret" not in data  # el secret nunca se expone


@pytest.mark.asyncio
async def test_create_webhook_short_secret(client, auth_headers_a):
    body = {**_VALID_BODY, "secret": "corto"}
    resp = await _create_webhook(client, auth_headers_a, body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_webhook_empty_events(client, auth_headers_a):
    body = {**_VALID_BODY, "events": []}
    resp = await _create_webhook(client, auth_headers_a, body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_webhooks_empty(client, auth_headers_b):
    resp = await client.get("/v1/webhooks", headers=auth_headers_b)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_webhooks_with_data(client, auth_headers_a, webhook_setup):
    resp = await client.get("/v1/webhooks", headers=auth_headers_a)
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert webhook_setup["id"] in ids


@pytest.mark.asyncio
async def test_get_webhook_detail(client, auth_headers_a, webhook_setup):
    resp = await client.get(f"/v1/webhooks/{webhook_setup['id']}", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json()["id"] == webhook_setup["id"]
    assert resp.json()["url"] == _VALID_BODY["url"]


@pytest.mark.asyncio
async def test_get_webhook_not_found(client, auth_headers_a):
    resp = await client.get(f"/v1/webhooks/{uid()}", headers=auth_headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_webhook(client, auth_headers_a, webhook_setup):
    resp = await client.patch(
        f"/v1/webhooks/{webhook_setup['id']}",
        json={"is_active": False, "events": ["stock.low"]},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["events"] == ["stock.low"]


@pytest.mark.asyncio
async def test_delete_webhook(client, auth_headers_a, webhook_setup):
    resp = await client.delete(f"/v1/webhooks/{webhook_setup['id']}", headers=auth_headers_a)
    assert resp.status_code == 204

    # Ya no debe existir
    resp2 = await client.get(f"/v1/webhooks/{webhook_setup['id']}", headers=auth_headers_a)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_webhook_not_found(client, auth_headers_a):
    resp = await client.delete(f"/v1/webhooks/{uid()}", headers=auth_headers_a)
    assert resp.status_code == 404


# ── T-401: Auth y aislamiento ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_requires_auth(client):
    resp = await _create_webhook(client, {})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_tenant_isolation(client, auth_headers_a, auth_headers_b, webhook_setup):
    """Tenant B no puede ver ni modificar los webhooks de Tenant A."""
    # GET: no visible para B
    resp = await client.get("/v1/webhooks", headers=auth_headers_b)
    ids = [w["id"] for w in resp.json()]
    assert webhook_setup["id"] not in ids

    # GET detail: 404 para B
    resp = await client.get(f"/v1/webhooks/{webhook_setup['id']}", headers=auth_headers_b)
    assert resp.status_code == 404

    # DELETE: 404 para B
    resp = await client.delete(f"/v1/webhooks/{webhook_setup['id']}", headers=auth_headers_b)
    assert resp.status_code == 404


# ── T-401: Test endpoint y entregas ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_test_endpoint_returns_result(client, auth_headers_a, webhook_setup):
    """El ping puede fallar (URL no existe) pero siempre retorna estructura válida."""
    resp = await client.post(f"/v1/webhooks/{webhook_setup['id']}/test", headers=auth_headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert "delivered" in data
    assert isinstance(data["delivered"], bool)


@pytest.mark.asyncio
async def test_get_deliveries_empty(client, auth_headers_a, webhook_setup):
    resp = await client.get(f"/v1/webhooks/{webhook_setup['id']}/deliveries", headers=auth_headers_a)
    assert resp.status_code == 200
    assert resp.json() == []


# ── T-402: dispatch_event y firma HMAC ────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_event_creates_delivery(db, client, tenant_a, auth_headers_a, webhook_setup):
    """dispatch_event inserta un registro en webhook_deliveries para el evento suscrito."""
    async with _TestSession() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": tenant_a["id"]},
        )
        await dispatch_event(
            session,
            tenant_a["id"],
            "transaction.receipt",
            {"transaction_id": uid(), "test": True},
        )
        await session.commit()

    # Verificar que se creó el delivery
    resp = await client.get(f"/v1/webhooks/{webhook_setup['id']}/deliveries", headers=auth_headers_a)
    assert resp.status_code == 200
    deliveries = resp.json()
    assert len(deliveries) == 1
    assert deliveries[0]["event_type"] == "transaction.receipt"
    assert deliveries[0]["status"] == "PENDING"
    assert deliveries[0]["attempts"] == 0


@pytest.mark.asyncio
async def test_dispatch_event_ignores_unsubscribed(db, client, tenant_a, auth_headers_a, webhook_setup):
    """Un evento al que el endpoint no está suscrito no genera delivery."""
    async with _TestSession() as session:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": tenant_a["id"]},
        )
        # "stock.low" no está en los eventos del webhook_setup
        await dispatch_event(session, tenant_a["id"], "stock.low", {"product_id": uid()})
        await session.commit()

    resp = await client.get(f"/v1/webhooks/{webhook_setup['id']}/deliveries", headers=auth_headers_a)
    assert resp.json() == []


@pytest.mark.asyncio
async def test_sign_payload_hmac():
    """La firma HMAC-SHA256 es verificable con el secreto correcto."""
    secret = "secreto-de-prueba-seguro"
    body = b'{"event": "ping"}'
    sig = sign_payload(secret, body)

    assert sig.startswith("sha256=")
    hex_part = sig[len("sha256="):]
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert hex_part == expected


@pytest.mark.asyncio
async def test_sign_payload_wrong_secret():
    """Un secreto incorrecto produce una firma diferente."""
    body = b'{"event": "test"}'
    sig_a = sign_payload("secreto-correcto-seguro", body)
    sig_b = sign_payload("secreto-incorrecto-ok", body)
    assert sig_a != sig_b
