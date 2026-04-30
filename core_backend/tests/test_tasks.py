"""
Tests de F-7 — Celery Tasks: send_email, check_expiring_api_keys, revoke_grace_period_key (RF-042, RF-043).

Todos los tests mockean Resend para que ninguna llamada real salga al exterior.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from tests.conftest import _TestSession


# ── Helpers ────────────────────────────────────────────────────────────────


async def _create_api_key_direct(tenant_id: str, name: str, expires_at: datetime, is_active: bool = True) -> str:
    key_uuid = str(uuid.uuid4())
    async with _TestSession() as session:
        await session.execute(
            text(
                "INSERT INTO api_keys (id, tenant_id, key_id, key_hash, name, scopes, "
                "ip_whitelist, expires_at, is_active, created_at) "
                "VALUES (:id, :tid, :kid, :kh, :name, '[]'::jsonb, '[]'::jsonb, :exp, :active, now())"
            ),
            {
                "id": key_uuid,
                "tid": tenant_id,
                "kid": f"mk_test_{uuid.uuid4().hex[:16]}",
                "kh": "testhash",
                "name": name,
                "exp": expires_at,
                "active": is_active,
            },
        )
        await session.commit()
    return key_uuid


async def _delete_api_key(key_id: str) -> None:
    async with _TestSession() as session:
        await session.execute(text("DELETE FROM api_keys WHERE id = :id"), {"id": key_id})
        await session.commit()


async def _key_is_active(key_id: str) -> bool:
    async with _TestSession() as session:
        result = await session.execute(
            text("SELECT is_active FROM api_keys WHERE id = :id"), {"id": key_id}
        )
        row = result.fetchone()
        return bool(row[0]) if row else False


# ── Tests: send_email ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_email_calls_resend():
    """send_email invoca resend.Emails.send con el template correcto."""
    mock_response = {"id": "email-123"}
    with patch("resend.Emails.send", return_value=mock_response) as mock_send:
        from app.tasks import send_email

        send_email(
            to_email="test@example.com",
            template="account_activation",
            context={
                "full_name": "Test User",
                "activation_url": "http://localhost/activate?token=abc",
            },
        )

        mock_send.assert_called_once()
        # SendParams is a TypedDict (dict); key "from" not "from_"
        call_params = mock_send.call_args[0][0]
        assert call_params["to"] == ["test@example.com"]
        assert "Activa" in call_params["subject"]
        assert "from" in call_params


@pytest.mark.asyncio
async def test_send_email_all_templates():
    """Todos los templates se renderizan sin KeyError."""
    from app.tasks import _TEMPLATES, send_email

    mock_response = {"id": "email-ok"}
    context_map = {
        "account_activation": {"full_name": "U", "activation_url": "http://x"},
        "activation_resent": {"full_name": "U", "activation_url": "http://x"},
        "password_changed": {"full_name": "U"},
        "api_key_expiring_30d": {"full_name": "U", "key_name": "K", "expires_at": "2026-12-01"},
        "api_key_expiring_7d": {"full_name": "U", "key_name": "K", "expires_at": "2026-12-01"},
        "api_key_expiring_1d": {"full_name": "U", "key_name": "K", "expires_at": "2026-12-01"},
        "api_key_expired": {"full_name": "U", "key_name": "K", "expires_at": "2026-12-01"},
        "api_key_rotated": {"full_name": "U", "key_name": "K"},
        "tenant_created": {"full_name": "U", "activation_url": "http://x"},
    }
    assert set(context_map.keys()) == set(_TEMPLATES.keys()), "Faltan templates en el test"

    with patch("resend.Emails.send", return_value=mock_response) as mock_send:
        for template, ctx in context_map.items():
            send_email(to_email="t@t.com", template=template, context=ctx)
        assert mock_send.call_count == len(context_map)


@pytest.mark.asyncio
async def test_send_email_unknown_template_raises():
    """Template desconocido lanza ValueError."""
    from app.tasks import send_email

    with pytest.raises(ValueError, match="Template desconocido"):
        send_email(to_email="t@t.com", template="nonexistent_template", context={})


@pytest.mark.asyncio
async def test_send_email_no_real_calls():
    """Verificación explícita: sin mock, resend.Emails.send no llama a la red en tests."""
    mock_send = MagicMock(return_value={"id": "fake"})
    with patch("resend.Emails.send", mock_send):
        from app.tasks import send_email

        send_email(
            to_email="safe@test.com",
            template="password_changed",
            context={"full_name": "Safe User"},
        )
    mock_send.assert_called_once()


# ── Tests: revoke_grace_period_key ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_grace_period_key_success(tenant_a):
    """Revoca correctamente una key activa."""
    from app.tasks import _async_revoke_grace_period_key

    future = datetime.now(timezone.utc) + timedelta(days=30)
    key_id = await _create_api_key_direct(tenant_a["id"], "grace-key", future)
    try:
        result = await _async_revoke_grace_period_key(key_id)
        assert result["revoked"] is True
        assert await _key_is_active(key_id) is False
    finally:
        await _delete_api_key(key_id)


@pytest.mark.asyncio
async def test_revoke_grace_period_key_not_found():
    """Key inexistente devuelve revoked=False con reason not_found."""
    from app.tasks import _async_revoke_grace_period_key

    result = await _async_revoke_grace_period_key(str(uuid.uuid4()))
    assert result["revoked"] is False
    assert result["reason"] == "not_found"


@pytest.mark.asyncio
async def test_revoke_grace_period_key_already_inactive(tenant_a):
    """Key ya inactiva devuelve revoked=False con reason already_inactive."""
    from app.tasks import _async_revoke_grace_period_key

    past = datetime.now(timezone.utc) - timedelta(days=1)
    key_id = await _create_api_key_direct(tenant_a["id"], "inactive-key", past, is_active=False)
    try:
        result = await _async_revoke_grace_period_key(key_id)
        assert result["revoked"] is False
        assert result["reason"] == "already_inactive"
    finally:
        await _delete_api_key(key_id)


# ── Tests: check_expiring_api_keys ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_expiring_keys_detects_30d(tenant_a):
    """Detecta keys que vencen en exactamente 30 días."""
    from app.tasks import _async_check_expiring_api_keys

    future = datetime.now(timezone.utc) + timedelta(days=30)
    key_id = await _create_api_key_direct(tenant_a["id"], "exp-30d", future)
    try:
        with patch("app.tasks.send_email") as mock_task:
            mock_task.delay = MagicMock()
            result = await _async_check_expiring_api_keys()
            assert result["queued"] >= 1
    finally:
        await _delete_api_key(key_id)


@pytest.mark.asyncio
async def test_check_expiring_keys_expires_today(tenant_a):
    """Keys vencidas hoy se desactivan automáticamente."""
    from app.tasks import _async_check_expiring_api_keys

    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    key_id = await _create_api_key_direct(tenant_a["id"], "exp-today", today_midnight)
    try:
        with patch("app.tasks.send_email"):
            result = await _async_check_expiring_api_keys()
            assert result["expired"] >= 1
        assert await _key_is_active(key_id) is False
    finally:
        await _delete_api_key(key_id)


@pytest.mark.asyncio
async def test_check_expiring_keys_beat_schedule():
    """check_expiring_api_keys está registrada en el beat_schedule."""
    from app.tasks import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "check-expiring-api-keys-daily" in schedule
    task_cfg = schedule["check-expiring-api-keys-daily"]
    assert task_cfg["task"] == "app.tasks.check_expiring_api_keys"
