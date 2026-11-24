"""
Hallazgos de la revisión independiente de R-01 (fuera de la revisión de Deiby, anteriores a ella).

1. Reservas: confirmar, cancelar y expirar leían el estado sin bloquear la fila. Con varios workers
   (prod corre 4, cada uno con su bucle de expiración) o una cancelación por API a la vez, la misma
   reserva se liberaba dos veces: `available_qty` inflado y posible sobreventa.
2. Webhooks: el despacho usaba una sola sesión para todos los tenants, con commit al final y
   `except Exception: pass`. Un error tardío deshacía el estado de entregas YA enviadas por HTTP y el
   siguiente ciclo las reenviaba duplicadas (y en silencio).

Las pruebas solo tocan datos que crean ellas mismas (L-4).
"""
import asyncio
import json
import logging

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from app.services.reservation import expire_due_reservations
from tests.conftest import _create_warehouse, _create_zone, _TestSession, uid


# ── Reservas ───────────────────────────────────────────────────────────────

async def _product(db, tenant_id: str) -> str:
    pid = uid()
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, 'Producto concurrencia', 'UNIT', 0, 0, false, false, false, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": f"CC-{uid()[:6]}"},
    )
    await db.commit()
    return pid


@pytest_asyncio.fixture
async def env(db, tenant_a):
    tid = tenant_a["id"]
    wh = await _create_warehouse(db, tid, f"WH-CC-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-CC-{uid()[:6]}")
    return {"tid": tid, "wh": wh["id"], "zone": zone["id"], "product": await _product(db, tid)}


async def _reserva_activa(client, headers, env, qty: int = 4) -> str:
    recibo = await client.post(
        "/v1/transactions/receipts",
        json={"reference_type": "PURCHASE_ORDER", "reference_id": f"OC-{uid()[:6]}", "reason_code": "COMPRA",
              "warehouse_id": env["wh"], "zone_id": env["zone"],
              "items": [{"product_id": env["product"], "quantity": 10, "unit_cost": 100}]},
        headers=headers,
    )
    assert recibo.status_code == 201, recibo.text
    resp = await client.post(
        "/v1/reservations",
        json={"reference_type": "WORK_ORDER", "reference_id": f"OT-{uid()[:6]}",
              "items": [{"product_id": env["product"], "warehouse_id": env["wh"], "zone_id": env["zone"], "quantity": qty}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _saldo(env) -> dict:
    async with _TestSession() as s:
        row = (
            await s.execute(
                text("SELECT physical_qty, reserved_qty, available_qty FROM stock_balances "
                     "WHERE product_id = :pid AND zone_id = :zid"),
                {"pid": env["product"], "zid": env["zone"]},
            )
        ).mappings().one()
    return {k: float(v) for k, v in row.items()}


async def _mientras_otro_la_cancela(rid: str, accion):
    """Otro proceso (otro worker, otra petición) ya cambió el estado de la reserva y aún no confirma.
    `accion` debe esperar a que confirme y entonces ver que ya no está ACTIVE."""
    async with _TestSession() as otro:
        await otro.execute(text("UPDATE reservations SET status = 'CANCELLED' WHERE id = :id"), {"id": rid})
        tarea = asyncio.create_task(accion())
        await asyncio.sleep(0.8)
        assert not tarea.done(), "espera a que el otro proceso confirme"
        await otro.commit()
        return await asyncio.wait_for(tarea, timeout=10)


@pytest.mark.asyncio
async def test_cancelar_una_reserva_que_otro_proceso_esta_cerrando_no_la_libera_dos_veces(client, auth_headers_a, env):
    rid = await _reserva_activa(client, auth_headers_a, env)
    antes = await _saldo(env)
    assert antes["reserved_qty"] == 4.0

    resp = await _mientras_otro_la_cancela(
        rid, lambda: client.post(f"/v1/reservations/{rid}/cancel", headers=auth_headers_a)
    )

    assert resp.status_code == 409, resp.text
    assert await _saldo(env) == antes, "no se liberó por segunda vez"


@pytest.mark.asyncio
async def test_confirmar_una_reserva_que_otro_proceso_esta_cerrando_no_despacha(client, auth_headers_a, env):
    rid = await _reserva_activa(client, auth_headers_a, env)
    antes = await _saldo(env)

    resp = await _mientras_otro_la_cancela(
        rid,
        lambda: client.post(
            f"/v1/reservations/{rid}/confirm",
            json={"actual_quantity_to_issue": 4, "issue_reference": "INV-CC"},
            headers=auth_headers_a,
        ),
    )

    assert resp.status_code == 409, resp.text
    assert await _saldo(env) == antes


@pytest.mark.asyncio
async def test_expirar_una_reserva_que_otro_proceso_esta_cerrando_no_la_libera_dos_veces(client, auth_headers_a, env):
    rid = await _reserva_activa(client, auth_headers_a, env)
    async with _TestSession() as s:
        await s.execute(text("UPDATE reservations SET expires_at = now() - interval '1 minute' WHERE id = :id"), {"id": rid})
        await s.commit()
    antes = await _saldo(env)

    expiradas = await _mientras_otro_la_cancela(rid, lambda: expire_due_reservations([env["tid"]]))

    assert expiradas == 0
    assert await _saldo(env) == antes
    async with _TestSession() as s:
        estado = (await s.execute(text("SELECT status FROM reservations WHERE id = :id"), {"id": rid})).scalar_one()
    assert estado == "CANCELLED", "no la pisa con EXPIRED"


# ── Webhooks ───────────────────────────────────────────────────────────────

async def _endpoint_con_entrega(tenant_id: str, url: str, secret: str) -> tuple[str, str]:
    eid, did = uid(), uid()
    async with _TestSession() as s:
        await s.execute(
            text("INSERT INTO webhook_endpoints (id, tenant_id, url, secret, events) "
                 "VALUES (:id, :tid, :url, :secret, CAST(:ev AS JSONB))"),
            {"id": eid, "tid": tenant_id, "url": url, "secret": secret, "ev": json.dumps(["transaction.receipt"])},
        )
        await s.execute(
            text("INSERT INTO webhook_deliveries (id, tenant_id, endpoint_id, event_type, payload, status, attempts) "
                 "VALUES (:id, :tid, :eid, 'transaction.receipt', CAST('{\"ok\": true}' AS JSONB), 'PENDING', 0)"),
            {"id": did, "tid": tenant_id, "eid": eid},
        )
        await s.commit()
    return eid, did


async def _entrega(did: str):
    async with _TestSession() as s:
        return (
            await s.execute(text("SELECT status, attempts FROM webhook_deliveries WHERE id = :id"), {"id": did})
        ).mappings().one()


@pytest.mark.asyncio
async def test_un_fallo_en_una_entrega_no_hace_reenviar_las_que_ya_salieron(tenant_a, monkeypatch, caplog):
    from app.services import webhook as webhook_service

    _, buena = await _endpoint_con_entrega(tenant_a["id"], "https://hooks.example.com/buena", "secreto-bueno-de-16-chars")
    _, mala = await _endpoint_con_entrega(tenant_a["id"], "https://hooks.example.com/mala", "secreto-que-revienta-1234")

    enviados: list[str] = []

    async def post_falso(self, url, **kwargs):
        enviados.append(url)
        return httpx.Response(200, text="ok")

    firmar = webhook_service.sign_payload

    def firma_que_revienta(secret, body):
        if secret.startswith("secreto-que-revienta"):
            raise RuntimeError("fallo simulado al firmar")
        return firmar(secret, body)

    monkeypatch.setattr(httpx.AsyncClient, "post", post_falso)
    monkeypatch.setattr(webhook_service, "sign_payload", firma_que_revienta)

    with caplog.at_level(logging.ERROR):
        await webhook_service.dispatch_pending_webhooks([tenant_a["id"]])
        await webhook_service.dispatch_pending_webhooks([tenant_a["id"]])

    assert enviados.count("https://hooks.example.com/buena") == 1, "la que ya salió no se reenvía"
    assert (await _entrega(buena))["status"] == "DELIVERED"
    assert (await _entrega(mala))["status"] == "PENDING"
    assert any(mala in r.getMessage() for r in caplog.records), "el fallo queda en el log, no se traga"
