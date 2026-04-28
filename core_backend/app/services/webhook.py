import hashlib
import hmac as hmac_module
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.webhook import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookEndpointResponse,
    WebhookTestResponse,
    WebhookUpdate,
)

_BACKOFF_SECONDS = [30, 300, 1800]
_MAX_ATTEMPTS = 3


def sign_payload(secret: str, body: bytes) -> str:
    return "sha256=" + hmac_module.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _get_endpoint_or_404(db: AsyncSession, tenant_id: str, endpoint_id: str):
    row = (
        await db.execute(
            text(
                "SELECT id, tenant_id, url, secret, events, is_active, created_at, updated_at "
                "FROM webhook_endpoints WHERE id = :id AND tenant_id = :tid"
            ),
            {"id": endpoint_id, "tid": tenant_id},
        )
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint no encontrado")
    return row


def _row_to_response(row) -> WebhookEndpointResponse:
    events = row.events if isinstance(row.events, list) else json.loads(row.events)
    return WebhookEndpointResponse(
        id=str(row.id),
        url=row.url,
        events=events,
        is_active=bool(row.is_active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_endpoint(db: AsyncSession, tenant_id: str, body: WebhookCreate) -> WebhookEndpointResponse:
    eid = str(uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO webhook_endpoints (id, tenant_id, url, secret, events, is_active, created_at, updated_at) "
            "VALUES (:id, :tid, :url, :secret, CAST(:events AS JSONB), true, :now, :now)"
        ),
        {
            "id": eid,
            "tid": tenant_id,
            "url": str(body.url),
            "secret": body.secret,
            "events": json.dumps(body.events),
            "now": now,
        },
    )
    await db.commit()
    row = await _get_endpoint_or_404(db, tenant_id, eid)
    return _row_to_response(row)


async def list_endpoints(db: AsyncSession, tenant_id: str) -> list[WebhookEndpointResponse]:
    rows = (
        await db.execute(
            text(
                "SELECT id, tenant_id, url, secret, events, is_active, created_at, updated_at "
                "FROM webhook_endpoints WHERE tenant_id = :tid ORDER BY created_at DESC"
            ),
            {"tid": tenant_id},
        )
    ).fetchall()
    return [_row_to_response(r) for r in rows]


async def get_endpoint(db: AsyncSession, tenant_id: str, endpoint_id: str) -> WebhookEndpointResponse:
    row = await _get_endpoint_or_404(db, tenant_id, endpoint_id)
    return _row_to_response(row)


async def update_endpoint(
    db: AsyncSession, tenant_id: str, endpoint_id: str, body: WebhookUpdate
) -> WebhookEndpointResponse:
    await _get_endpoint_or_404(db, tenant_id, endpoint_id)

    updates: list[str] = []
    params: dict = {"id": endpoint_id, "tid": tenant_id, "now": datetime.now(timezone.utc)}

    if body.url is not None:
        updates.append("url = :url")
        params["url"] = str(body.url)
    if body.secret is not None:
        updates.append("secret = :secret")
        params["secret"] = body.secret
    if body.events is not None:
        updates.append("events = CAST(:events AS JSONB)")
        params["events"] = json.dumps(body.events)
    if body.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = body.is_active

    if updates:
        updates.append("updated_at = :now")
        await db.execute(
            text(f"UPDATE webhook_endpoints SET {', '.join(updates)} WHERE id = :id AND tenant_id = :tid"),
            params,
        )
        await db.commit()

    return _row_to_response(await _get_endpoint_or_404(db, tenant_id, endpoint_id))


async def delete_endpoint(db: AsyncSession, tenant_id: str, endpoint_id: str) -> None:
    await _get_endpoint_or_404(db, tenant_id, endpoint_id)
    await db.execute(
        text("DELETE FROM webhook_endpoints WHERE id = :id AND tenant_id = :tid"),
        {"id": endpoint_id, "tid": tenant_id},
    )
    await db.commit()


async def test_endpoint_ping(db: AsyncSession, tenant_id: str, endpoint_id: str) -> WebhookTestResponse:
    row = await _get_endpoint_or_404(db, tenant_id, endpoint_id)
    payload = json.dumps(
        {"event": "ping", "timestamp": datetime.now(timezone.utc).isoformat(), "endpoint_id": endpoint_id}
    ).encode()
    sig = sign_payload(row.secret, payload)

    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            resp = await http_client.post(
                row.url,
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": sig,
                    "X-Webhook-Event": "ping",
                },
            )
        return WebhookTestResponse(delivered=resp.status_code < 300, response_code=resp.status_code)
    except Exception as exc:
        return WebhookTestResponse(delivered=False, response_code=None, error=str(exc)[:200])


async def dispatch_event(db: AsyncSession, tenant_id: str, event_type: str, payload: dict) -> None:
    """Crea registros de entrega para todos los endpoints activos suscritos al evento.

    No hace commit — el caller es responsable de confirmar la transacción.
    """
    rows = (
        await db.execute(
            text("SELECT id, events FROM webhook_endpoints WHERE tenant_id = :tid AND is_active = true"),
            {"tid": tenant_id},
        )
    ).fetchall()

    now = datetime.now(timezone.utc)
    for row in rows:
        events = row.events if isinstance(row.events, list) else json.loads(row.events)
        if event_type not in events:
            continue
        await db.execute(
            text(
                "INSERT INTO webhook_deliveries "
                "(id, tenant_id, endpoint_id, event_type, payload, status, attempts, created_at) "
                "VALUES (:id, :tid, :eid, :et, CAST(:payload AS JSONB), 'PENDING', 0, :now)"
            ),
            {
                "id": str(uuid4()),
                "tid": tenant_id,
                "eid": str(row.id),
                "et": event_type,
                "payload": json.dumps(payload),
                "now": now,
            },
        )


async def get_deliveries(db: AsyncSession, tenant_id: str, endpoint_id: str) -> list[WebhookDeliveryResponse]:
    await _get_endpoint_or_404(db, tenant_id, endpoint_id)
    rows = (
        await db.execute(
            text(
                "SELECT id, event_type, status, attempts, last_response_code, last_response_body, "
                "       next_attempt_at, created_at "
                "FROM webhook_deliveries WHERE endpoint_id = :eid AND tenant_id = :tid "
                "ORDER BY created_at DESC LIMIT 100"
            ),
            {"eid": endpoint_id, "tid": tenant_id},
        )
    ).fetchall()
    return [
        WebhookDeliveryResponse(
            id=str(r.id),
            event_type=r.event_type,
            status=r.status,
            attempts=r.attempts,
            last_response_code=r.last_response_code,
            next_attempt_at=r.next_attempt_at,
            created_at=r.created_at,
        )
        for r in rows
    ]
