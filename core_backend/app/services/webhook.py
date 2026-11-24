import hashlib
import hmac as hmac_module
import json
import logging
from datetime import datetime, timedelta, timezone
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

logger = logging.getLogger(__name__)

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


# ── Despacho de entregas pendientes (bucle de fondo) ─────────────────────────

_PENDIENTE_SQL = (
    "SELECT wd.id, wd.event_type, wd.payload, wd.attempts, we.url, we.secret "
    "FROM webhook_deliveries wd JOIN webhook_endpoints we ON wd.endpoint_id = we.id "
    "WHERE wd.tenant_id = :tid AND wd.status = 'PENDING' "
    "AND (wd.next_attempt_at IS NULL OR wd.next_attempt_at <= now())"
)


async def dispatch_pending_webhooks(tenant_ids: list[str] | None = None) -> int:
    """Entrega los webhooks pendientes. `tenant_ids` limita los tenants (los tests lo usan para no tocar
    datos ajenos); sin él, todos. Devuelve cuántas entregas quedaron DELIVERED.

    Cada entrega va en su propia transacción y se reclama con `FOR UPDATE SKIP LOCKED`:
    - un error en una entrega se registra y no deshace el estado de las que ya salieron (antes una sola
      sesión con commit al final y `except: pass` las reenviaba duplicadas en el siguiente ciclo);
    - varios workers (prod corre 4, cada uno con su bucle) no envían la misma entrega a la vez.
    Entrega «al menos una vez»: si el commit falla después del POST, se reintenta en el siguiente ciclo.
    """
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal, set_tenant_context

    if tenant_ids is None:
        async with AsyncSessionLocal() as session:
            # `tenants` no está bajo RLS
            tenant_ids = [str(r.id) for r in (await session.execute(text("SELECT id FROM tenants"))).fetchall()]

    entregadas = 0
    for tid in tenant_ids:
        try:
            async with AsyncSessionLocal() as session:
                await set_tenant_context(session, tid)
                ids = [str(r.id) for r in (await session.execute(text(_PENDIENTE_SQL), {"tid": tid})).fetchall()]
        except Exception:
            logger.exception("No se pudieron listar los webhooks pendientes del tenant %s; sigue con los demás", tid)
            continue

        for did in ids:
            try:
                async with AsyncSessionLocal() as session:
                    await set_tenant_context(session, tid)
                    if await _deliver_one(session, tid, did, settings):
                        entregadas += 1
                    await session.commit()
            except Exception:
                logger.exception("No se pudo despachar la entrega de webhook %s del tenant %s; sigue con las demás", did, tid)
    return entregadas


async def _deliver_one(db: AsyncSession, tenant_id: str, delivery_id: str, settings) -> bool:
    """Reclama la entrega (si otro worker la tiene, la salta), hace el POST y guarda el resultado."""
    row = (
        await db.execute(
            text(_PENDIENTE_SQL + " AND wd.id = :id FOR UPDATE OF wd SKIP LOCKED"),
            {"tid": tenant_id, "id": delivery_id},
        )
    ).fetchone()
    if row is None:
        return False

    payload_bytes = json.dumps(row.payload).encode()
    signature = sign_payload(row.secret, payload_bytes)
    try:
        async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as http:
            resp = await http.post(
                row.url,
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": row.event_type,
                },
            )
        delivered = resp.status_code < 300
        last_code: int | None = resp.status_code
        last_body = resp.text[:1000]
    except Exception as exc:  # el destino no respondió: es un intento fallido, no un error nuestro
        delivered = False
        last_code = None
        last_body = str(exc)[:1000]

    attempts = row.attempts + 1
    next_attempt = None
    if delivered:
        new_status = "DELIVERED"
    elif attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
        new_status = "FAILED"
    else:
        new_status = "PENDING"
        backoff = _BACKOFF_SECONDS[min(attempts - 1, len(_BACKOFF_SECONDS) - 1)]
        next_attempt = datetime.now(timezone.utc) + timedelta(seconds=backoff)

    await db.execute(
        text(
            "UPDATE webhook_deliveries "
            "SET status = :s, attempts = :a, last_response_code = :lc, "
            "    last_response_body = :lb, next_attempt_at = :na "
            "WHERE id = :id"
        ),
        {"s": new_status, "a": attempts, "lc": last_code, "lb": last_body, "na": next_attempt, "id": delivery_id},
    )
    return delivered
