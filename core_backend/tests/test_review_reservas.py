"""
Revisión 2026-11-19 — R-01 y R-02 (reservas).

R-01: una reserva que falla al liberarse detenía la expiración de TODOS los tenants, en silencio
      (una sola sesión, commit al final y `except Exception: pass`).
R-02: las reservas anteriores a la migración 015 (sin asignaciones) se liberaban contra la fila de
      saldo equivocada (la sin lote aunque no tuviera nada reservado) → 409, imposibles de cancelar,
      confirmar o expirar.

Las pruebas solo tocan datos que crean ellas mismas (L-4): la expiración se limita al tenant del test.
"""
import logging

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.services.reservation import expire_due_reservations
from tests.conftest import _create_warehouse, _create_zone, _TestSession, uid


async def _product(db, tenant_id: str, *, track_lots: bool) -> str:
    pid = uid()
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, 'Producto revisión', 'UNIT', 0, 0, false, :lots, false, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": f"REV-{uid()[:6]}", "lots": track_lots},
    )
    await db.commit()
    return pid


@pytest_asyncio.fixture
async def env(db, tenant_a):
    tid = tenant_a["id"]
    wh = await _create_warehouse(db, tid, f"WH-RV-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-RV-{uid()[:6]}")
    return {
        "tid": tid, "wh": wh["id"], "zone": zone["id"],
        "plain_1": await _product(db, tid, track_lots=False),
        "plain_2": await _product(db, tid, track_lots=False),
        "lots": await _product(db, tid, track_lots=True),
    }


async def _receipt(client, headers, env, product_id: str, qty: int, lot: str | None = None) -> None:
    item = {"product_id": product_id, "quantity": qty, "unit_cost": 100}
    if lot:
        item["lot_number"] = lot
    resp = await client.post(
        "/v1/transactions/receipts",
        json={
            "reference_type": "PURCHASE_ORDER", "reference_id": f"OC-{uid()[:6]}", "reason_code": "COMPRA",
            "warehouse_id": env["wh"], "zone_id": env["zone"], "items": [item],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


async def _reserve(client, headers, env, product_id: str, qty: int) -> str:
    resp = await client.post(
        "/v1/reservations",
        json={
            "reference_type": "WORK_ORDER", "reference_id": f"OT-{uid()[:6]}",
            "items": [{"product_id": product_id, "warehouse_id": env["wh"], "zone_id": env["zone"], "quantity": qty}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _status(reservation_id: str) -> str:
    async with _TestSession() as s:
        return (await s.execute(text("SELECT status FROM reservations WHERE id = :id"), {"id": reservation_id})).scalar_one()


async def _balance(balance_id: str) -> dict:
    async with _TestSession() as s:
        row = (
            await s.execute(
                text("SELECT physical_qty, reserved_qty, available_qty FROM stock_balances WHERE id = :id"),
                {"id": balance_id},
            )
        ).mappings().one()
    return {k: float(v) for k, v in row.items()}


async def _balance_id(product_id: str, zone_id: str, lot: str | None) -> str:
    async with _TestSession() as s:
        return str(
            (
                await s.execute(
                    text(
                        "SELECT id FROM stock_balances WHERE product_id = :pid AND zone_id = :zid "
                        "AND lot_number IS NOT DISTINCT FROM :lot"
                    ),
                    {"pid": product_id, "zid": zone_id, "lot": lot},
                )
            ).scalar_one()
        )


async def _sql(sql: str, **params) -> None:
    async with _TestSession() as s:
        await s.execute(text(sql), params)
        await s.commit()


# ── R-01 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_r01_una_reserva_que_falla_no_detiene_la_expiracion_de_las_demas(client, auth_headers_a, env, caplog):
    await _receipt(client, auth_headers_a, env, env["plain_1"], 10)
    await _receipt(client, auth_headers_a, env, env["plain_2"], 10)
    mala = await _reserve(client, auth_headers_a, env, env["plain_1"], 2)
    buena = await _reserve(client, auth_headers_a, env, env["plain_2"], 2)

    for rid in (mala, buena):
        await _sql("UPDATE reservations SET expires_at = now() - interval '1 minute' WHERE id = :id", id=rid)
    # La "mala" ya no encuentra lo que apartó: liberar daría reserved_qty negativo (409)
    await _sql("UPDATE stock_balances SET reserved_qty = 0 WHERE id = :id",
               id=await _balance_id(env["plain_1"], env["zone"], None))

    with caplog.at_level(logging.ERROR):
        expiradas = await expire_due_reservations([env["tid"]])

    assert expiradas == 1
    assert await _status(buena) == "EXPIRED", "la reserva sana expira aunque otra falle"
    assert await _status(mala) == "ACTIVE"
    assert any(mala in r.getMessage() for r in caplog.records), "el fallo queda en el log, no se traga"
    sano = await _balance(await _balance_id(env["plain_2"], env["zone"], None))
    assert sano == {"physical_qty": 10.0, "reserved_qty": 0.0, "available_qty": 10.0}, "la sana devolvió lo apartado"
    roto = await _balance(await _balance_id(env["plain_1"], env["zone"], None))
    assert roto["reserved_qty"] == 0.0 and roto["physical_qty"] == 10.0, "la que falló no dejó el saldo a medias"


# ── R-02 ───────────────────────────────────────────────────────────────────

async def _legacy_reservation(env, product_id: str, qty: int) -> str:
    """Una reserva como las de antes de la 015: con ítem, sin asignaciones."""
    rid = uid()
    await _sql(
        "INSERT INTO reservations (id, tenant_id, reference_type, reference_id, status, expires_at, created_at, updated_at) "
        "VALUES (:id, :tid, 'WORK_ORDER', 'OT-LEGACY', 'ACTIVE', now() + interval '1 hour', now(), now())",
        id=rid, tid=env["tid"],
    )
    await _sql(
        "INSERT INTO reservation_items (id, reservation_id, tenant_id, product_id, warehouse_id, zone_id, quantity, confirmed_qty) "
        "VALUES (:id, :rid, :tid, :pid, :wid, :zid, :qty, 0)",
        id=uid(), rid=rid, tid=env["tid"], pid=product_id, wid=env["wh"], zid=env["zone"], qty=qty,
    )
    return rid


async def _escenario_r02(client, headers, env) -> tuple[str, str]:
    """Saldo con lote L-1 (5, todo reservado por la reserva antigua) y saldo sin lote (4, nada reservado)."""
    await _receipt(client, headers, env, env["lots"], 5, lot="L-1")
    con_lote = await _balance_id(env["lots"], env["zone"], "L-1")
    await _sql("UPDATE stock_balances SET reserved_qty = 5, available_qty = 0 WHERE id = :id", id=con_lote)
    sin_lote = uid()
    await _sql(
        "INSERT INTO stock_balances (id, tenant_id, product_id, warehouse_id, zone_id, lot_number, "
        " physical_qty, reserved_qty, available_qty) VALUES (:id, :tid, :pid, :wid, :zid, NULL, 4, 0, 4)",
        id=sin_lote, tid=env["tid"], pid=env["lots"], wid=env["wh"], zid=env["zone"],
    )
    return con_lote, sin_lote


@pytest.mark.asyncio
async def test_r02_cancelar_una_reserva_antigua_libera_el_saldo_que_de_verdad_la_tiene(client, auth_headers_a, env):
    con_lote, sin_lote = await _escenario_r02(client, auth_headers_a, env)
    rid = await _legacy_reservation(env, env["lots"], 5)

    resp = await client.post(f"/v1/reservations/{rid}/cancel", headers=auth_headers_a)
    assert resp.status_code == 200, resp.text
    assert await _balance(con_lote) == {"physical_qty": 5.0, "reserved_qty": 0.0, "available_qty": 5.0}
    assert await _balance(sin_lote) == {"physical_qty": 4.0, "reserved_qty": 0.0, "available_qty": 4.0}


@pytest.mark.asyncio
async def test_r02_confirmar_una_reserva_antigua_despacha_del_saldo_reservado(client, auth_headers_a, env):
    con_lote, sin_lote = await _escenario_r02(client, auth_headers_a, env)
    rid = await _legacy_reservation(env, env["lots"], 5)

    resp = await client.post(
        f"/v1/reservations/{rid}/confirm",
        json={"actual_quantity_to_issue": 5, "issue_reference": "INV-LEG"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200, resp.text
    assert await _balance(con_lote) == {"physical_qty": 0.0, "reserved_qty": 0.0, "available_qty": 0.0}
    assert await _balance(sin_lote) == {"physical_qty": 4.0, "reserved_qty": 0.0, "available_qty": 4.0}


@pytest.mark.asyncio
async def test_r02_una_reserva_antigua_vencida_expira(client, auth_headers_a, env):
    con_lote, _ = await _escenario_r02(client, auth_headers_a, env)
    rid = await _legacy_reservation(env, env["lots"], 5)
    await _sql("UPDATE reservations SET expires_at = now() - interval '1 minute' WHERE id = :id", id=rid)

    await expire_due_reservations([env["tid"]])

    assert await _status(rid) == "EXPIRED"
    assert await _balance(con_lote) == {"physical_qty": 5.0, "reserved_qty": 0.0, "available_qty": 5.0}


@pytest.mark.asyncio
async def test_r02_lo_reservado_repartido_en_varias_filas_se_libera_de_todas(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, env["lots"], 3, lot="L-A")
    await _receipt(client, auth_headers_a, env, env["lots"], 2, lot="L-B")
    a = await _balance_id(env["lots"], env["zone"], "L-A")
    b = await _balance_id(env["lots"], env["zone"], "L-B")
    await _sql("UPDATE stock_balances SET reserved_qty = 3, available_qty = 0 WHERE id = :id", id=a)
    await _sql("UPDATE stock_balances SET reserved_qty = 2, available_qty = 0 WHERE id = :id", id=b)
    rid = await _legacy_reservation(env, env["lots"], 5)

    resp = await client.post(f"/v1/reservations/{rid}/cancel", headers=auth_headers_a)
    assert resp.status_code == 200, resp.text
    assert (await _balance(a))["reserved_qty"] == 0.0
    assert (await _balance(b))["reserved_qty"] == 0.0


@pytest.mark.asyncio
async def test_r02_si_no_alcanza_lo_reservado_responde_409_con_motivo(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, env["lots"], 5, lot="L-1")
    con_lote = await _balance_id(env["lots"], env["zone"], "L-1")
    await _sql("UPDATE stock_balances SET reserved_qty = 2, available_qty = 3 WHERE id = :id", id=con_lote)
    rid = await _legacy_reservation(env, env["lots"], 5)

    resp = await client.post(f"/v1/reservations/{rid}/cancel", headers=auth_headers_a)
    assert resp.status_code == 409
    assert "reservado" in resp.json()["detail"]
    assert await _balance(con_lote) == {"physical_qty": 5.0, "reserved_qty": 2.0, "available_qty": 3.0}


# ── Ajustes tras la revisión independiente del grupo ───────────────────────

@pytest.mark.asyncio
async def test_r02_una_reserva_antigua_no_se_lleva_lo_apartado_por_una_nueva(client, auth_headers_a, env):
    """Misma zona, una reserva de antes de la 015 (5 sin lote) y otra nueva (8 del lote L-NUEVA, con
    asignaciones). `reserved_qty` suma las dos: al cancelar la antigua hay que liberar SU fila, no la que
    más tiene reservado (que es la de la nueva)."""
    await _receipt(client, auth_headers_a, env, env["lots"], 20, lot="L-NUEVA")
    y = await _balance_id(env["lots"], env["zone"], "L-NUEVA")
    x = uid()
    await _sql(
        "INSERT INTO stock_balances (id, tenant_id, product_id, warehouse_id, zone_id, lot_number, "
        " physical_qty, reserved_qty, available_qty) VALUES (:id, :tid, :pid, :wid, :zid, NULL, 5, 5, 0)",
        id=x, tid=env["tid"], pid=env["lots"], wid=env["wh"], zid=env["zone"],
    )
    antigua = await _legacy_reservation(env, env["lots"], 5)
    nueva = await _reserve(client, auth_headers_a, env, env["lots"], 8)
    assert (await _balance(y))["reserved_qty"] == 8.0

    cancelar_antigua = await client.post(f"/v1/reservations/{antigua}/cancel", headers=auth_headers_a)
    assert cancelar_antigua.status_code == 200, cancelar_antigua.text
    assert await _balance(x) == {"physical_qty": 5.0, "reserved_qty": 0.0, "available_qty": 5.0}
    assert (await _balance(y))["reserved_qty"] == 8.0, "lo apartado por la reserva nueva no se toca"

    cancelar_nueva = await client.post(f"/v1/reservations/{nueva}/cancel", headers=auth_headers_a)
    assert cancelar_nueva.status_code == 200, cancelar_nueva.text
    assert await _balance(y) == {"physical_qty": 20.0, "reserved_qty": 0.0, "available_qty": 20.0}


@pytest.mark.asyncio
async def test_r01_un_tenant_que_falla_al_prepararse_no_detiene_a_los_demas(client, auth_headers_a, env, monkeypatch):
    await _receipt(client, auth_headers_a, env, env["plain_1"], 10)
    rid = await _reserve(client, auth_headers_a, env, env["plain_1"], 2)
    await _sql("UPDATE reservations SET expires_at = now() - interval '1 minute' WHERE id = :id", id=rid)

    from app.core import database

    original = database.set_tenant_context
    tenant_roto = uid()

    async def falla_para_uno(session, tenant_id):
        if tenant_id == tenant_roto:
            raise RuntimeError("fallo simulado al fijar el tenant")
        return await original(session, tenant_id)

    monkeypatch.setattr(database, "set_tenant_context", falla_para_uno)

    expiradas = await expire_due_reservations([tenant_roto, env["tid"]])  # el roto va primero

    assert expiradas == 1
    assert await _status(rid) == "EXPIRED"
