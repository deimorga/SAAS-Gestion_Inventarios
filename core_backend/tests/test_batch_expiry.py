"""
Corregir o quitar el vencimiento de un lote ya registrado — PATCH /v1/batches/{id}.

Caso real: el lote C-202611-13 del cable ELE-CABLE-N8 quedó con vencimiento 13/11/2026, que era la
fecha de ingreso. Figuraba vencido y, al apartar, salía de primero (FEFO).

Quitar el vencimiento tiene que contar como «sin vencimiento» de verdad. Antes de este cambio el
atajo del ledger lo habría revivido en tres sitios (reservas, detalle de la reserva y saldos) y la
siguiente entrada del lote lo habría vuelto a rellenar. Por eso el lote guarda `expiry_overridden`.

Escenarios:
  - Cambiar la fecha y quitarla; el lote, los saldos, las reservas y el reporte la respetan
  - Una entrada posterior del mismo lote no la devuelve
  - Lotes anteriores sin registro de vencimiento siguen usando el ledger hasta que se corrijan
  - El ledger no se toca (inmutable)
  - Validaciones, permisos, aislamiento entre tenants y auditoría
"""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text

from tests.conftest import (
    _audit_rows,
    _create_warehouse,
    _create_zone,
    _delete_user_by_id,
    _insert_user,
    _TestSession,
    uid,
)


def _in(days: int) -> str:
    """Fecha relativa a hoy, para que las pruebas no caduquen."""
    return (date.today() + timedelta(days=days)).isoformat()


# ── Helpers ────────────────────────────────────────────────────────────────

async def _product(db, tenant_id: str, *, track_expiry: bool = False) -> str:
    pid = uid()
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, :name, 'UNIT', 0, 0, false, true, :te, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": f"VEN-{uid()[:6]}", "name": "Producto con lotes", "te": track_expiry},
    )
    await db.commit()
    return pid


@pytest_asyncio.fixture
async def env(db, tenant_a):
    tid = tenant_a["id"]
    wh = await _create_warehouse(db, tid, f"WH-VE-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-VE-{uid()[:6]}")
    return {"tid": tid, "wh": wh["id"], "zone": zone["id"], "product": await _product(db, tid)}


async def _receipt(client, headers, env, lot: str, qty: int = 5, expiry: str | None = None, product: str | None = None):
    item = {"product_id": product or env["product"], "quantity": qty, "unit_cost": 100, "lot_number": lot}
    if expiry:
        item["expiry_date"] = expiry
    resp = await client.post(
        "/v1/transactions/receipts",
        json={
            "reference_type": "PURCHASE_ORDER", "reference_id": f"OC-{uid()[:6]}", "reason_code": "COMPRA",
            "warehouse_id": env["wh"], "zone_id": env["zone"], "items": [item],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


async def _batch(client, headers, env, lot: str, product: str | None = None) -> dict:
    resp = await client.get("/v1/batches", params={"product_id": product or env["product"]}, headers=headers)
    assert resp.status_code == 200, resp.text
    return next(b for b in resp.json() if b["batch_number"] == lot)


async def _patch(client, headers, batch_id: str, body: dict):
    return await client.patch(f"/v1/batches/{batch_id}", json=body, headers=headers)


async def _balance_expiry(client, headers, lot: str):
    resp = await client.get("/v1/stock/balances", params={"lot_number": lot}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"][0]["expiry_date"]


async def _reserve(client, headers, env, qty: int) -> dict:
    resp = await client.post(
        "/v1/reservations",
        json={
            "reference_type": "WORK_ORDER", "reference_id": f"OT-{uid()[:6]}",
            "items": [{"product_id": env["product"], "warehouse_id": env["wh"], "zone_id": env["zone"], "quantity": qty}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Cambiar y quitar la fecha ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_corregir_la_fecha_de_vencimiento(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")

    resp = await _patch(client, auth_headers_a, batch["id"], {"expiry_date": _in(365)})
    assert resp.status_code == 200, resp.text
    assert resp.json()["expiry_date"] == _in(365)

    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] == _in(365)
    assert await _balance_expiry(client, auth_headers_a, "L-ERR") == _in(365)


@pytest.mark.asyncio
async def test_quitar_el_vencimiento_del_lote(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")

    resp = await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["expiry_date"] is None
    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] is None


@pytest.mark.asyncio
async def test_sin_vencimiento_de_verdad_en_los_saldos(client, auth_headers_a, env):
    """El saldo no vuelve a la fecha del movimiento de entrada, que sigue en el ledger."""
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    assert await _balance_expiry(client, auth_headers_a, "L-ERR") == _in(1)

    batch = await _batch(client, auth_headers_a, env, "L-ERR")
    assert (await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})).status_code == 200

    assert await _balance_expiry(client, auth_headers_a, "L-ERR") is None


@pytest.mark.asyncio
async def test_el_ledger_no_se_toca(client, auth_headers_a, env):
    """El ledger es inmutable (C-4): el movimiento conserva la fecha con la que se registró."""
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")
    await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})

    resp = await client.get("/v1/ledger", params={"lot_number": "L-ERR"}, headers=auth_headers_a)
    assert resp.status_code == 200
    assert [e["expiry_date"] for e in resp.json()["data"]] == [_in(1)]


@pytest.mark.asyncio
async def test_la_reserva_ya_no_aparta_primero_un_lote_sin_vencimiento(client, auth_headers_a, env):
    """El caso del brief: el lote con la fecha equivocada salía de primero."""
    await _receipt(client, auth_headers_a, env, "LOT-OK", qty=5, expiry=_in(60))
    await _receipt(client, auth_headers_a, env, "LOT-ERR", qty=5, expiry=_in(1))

    antes = await _reserve(client, auth_headers_a, env, 3)
    assert [a["lot_number"] for a in antes["items"][0]["allocations"]] == ["LOT-ERR"], "FEFO: el que vence antes"
    await client.post(f"/v1/reservations/{antes['id']}/cancel", headers=auth_headers_a)

    batch = await _batch(client, auth_headers_a, env, "LOT-ERR")
    assert (await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})).status_code == 200

    despues = await _reserve(client, auth_headers_a, env, 8)
    allocs = despues["items"][0]["allocations"]
    assert [a["lot_number"] for a in allocs] == ["LOT-OK", "LOT-ERR"], "el lote sin vencimiento va al final"
    assert allocs[0]["expiry_date"] == _in(60)
    assert allocs[1]["expiry_date"] is None, "el detalle de la reserva tampoco revive la fecha del ledger"


@pytest.mark.asyncio
async def test_una_entrada_posterior_no_devuelve_el_vencimiento_quitado(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")
    await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})

    await _receipt(client, auth_headers_a, env, "L-ERR", qty=2, expiry=_in(30))

    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] is None
    assert await _balance_expiry(client, auth_headers_a, "L-ERR") is None


@pytest.mark.asyncio
async def test_sin_corregir_una_entrada_posterior_si_rellena_un_vencimiento_vacio(client, auth_headers_a, env):
    """Compatibilidad: sin una corrección manual, el comportamiento de siempre no cambia."""
    await _receipt(client, auth_headers_a, env, "L-NUEVO", qty=2)
    batch = await _batch(client, auth_headers_a, env, "L-NUEVO")
    assert batch["expiry_date"] is None

    await _receipt(client, auth_headers_a, env, "L-NUEVO", qty=2, expiry=_in(30))
    assert (await _batch(client, auth_headers_a, env, "L-NUEVO"))["expiry_date"] == _in(30)


@pytest.mark.asyncio
async def test_lote_anterior_sin_fecha_en_su_registro_sigue_usando_el_ledger_hasta_corregirlo(
    client, auth_headers_a, env
):
    """Lotes de antes de que las entradas crearan lotes: su fecha solo está en el ledger."""
    await _receipt(client, auth_headers_a, env, "L-VIEJO", expiry=_in(20))
    batch = await _batch(client, auth_headers_a, env, "L-VIEJO")
    async with _TestSession() as session:
        await session.execute(text("UPDATE batches SET expiry_date = NULL WHERE id = :id"), {"id": batch["id"]})
        await session.commit()

    assert await _balance_expiry(client, auth_headers_a, "L-VIEJO") == _in(20), "el atajo del ledger se mantiene"

    assert (await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})).status_code == 200
    assert await _balance_expiry(client, auth_headers_a, "L-VIEJO") is None, "tras corregirlo, ya no"


@pytest.mark.asyncio
async def test_el_reporte_de_lotes_por_vencer_excluye_el_lote_sin_vencimiento(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(5))
    antes = await client.get("/v1/reports/expiring", params={"days_ahead": 30}, headers=auth_headers_a)
    assert "L-ERR" in antes.text

    batch = await _batch(client, auth_headers_a, env, "L-ERR")
    await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})

    despues = await client.get("/v1/reports/expiring", params={"days_ahead": 30}, headers=auth_headers_a)
    assert despues.status_code == 200
    assert "L-ERR" not in despues.text


# ── Validaciones ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_un_producto_que_exige_vencimiento_no_puede_quedar_sin_el(client, auth_headers_a, db, env):
    pid = await _product(db, env["tid"], track_expiry=True)
    await _receipt(client, auth_headers_a, env, "L-EXIGE", expiry=_in(10), product=pid)
    batch = await _batch(client, auth_headers_a, env, "L-EXIGE", product=pid)

    quitar = await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})
    assert quitar.status_code == 422
    assert "track_expiry" in quitar.json()["detail"]
    assert (await _batch(client, auth_headers_a, env, "L-EXIGE", product=pid))["expiry_date"] == _in(10)

    cambiar = await _patch(client, auth_headers_a, batch["id"], {"expiry_date": _in(40)})
    assert cambiar.status_code == 200


@pytest.mark.asyncio
async def test_el_vencimiento_no_puede_ser_anterior_a_la_fabricacion(client, auth_headers_a, env):
    created = await client.post(
        "/v1/batches",
        json={
            "product_id": env["product"], "batch_number": "L-FAB", "initial_qty": 5,
            "manufactured_date": _in(-30), "expiry_date": _in(100),
        },
        headers=auth_headers_a,
    )
    assert created.status_code == 201, created.text

    resp = await _patch(client, auth_headers_a, created.json()["id"], {"expiry_date": _in(-60)})
    assert resp.status_code == 422
    assert (await _batch(client, auth_headers_a, env, "L-FAB"))["expiry_date"] == _in(100)


@pytest.mark.asyncio
async def test_el_cuerpo_debe_traer_expiry_date_y_nada_mas(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")

    assert (await _patch(client, auth_headers_a, batch["id"], {})).status_code == 422, "vacío no es «quitar»"
    assert (await _patch(client, auth_headers_a, batch["id"], {"expiry_date": "no-es-fecha"})).status_code == 422
    assert (await _patch(client, auth_headers_a, batch["id"], {"initial_qty": 99})).status_code == 422
    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] == _in(1)


@pytest.mark.asyncio
async def test_lote_inexistente_o_de_otro_tenant_es_404(client, auth_headers_a, auth_headers_b, env, db, tenant_b):
    assert (await _patch(client, auth_headers_a, str(uuid.uuid4()), {"expiry_date": None})).status_code == 404

    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")
    resp = await _patch(client, auth_headers_b, batch["id"], {"expiry_date": None})
    assert resp.status_code == 404
    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] == _in(1)


@pytest.mark.asyncio
async def test_un_viewer_no_puede_corregir_el_vencimiento(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")

    email = f"viewer-{uuid.uuid4().hex[:8]}@corp.com"
    viewer_id = await _insert_user(email, env["tid"], "viewer")
    try:
        login = await client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await _patch(client, headers, batch["id"], {"expiry_date": None})).status_code == 403
    finally:
        await _delete_user_by_id(viewer_id)
    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] == _in(1)


# ── Auditoría ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_la_correccion_queda_en_la_auditoria(client, auth_headers_a, env, user_a):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")

    resp = await _patch(client, auth_headers_a, batch["id"], {"expiry_date": None})
    assert resp.status_code == 200, resp.text

    (row,) = await _audit_rows(batch["id"], "UPDATE")
    assert row["entity"] == "batches"
    assert row["old_values"]["expiry_date"] == _in(1)
    assert row["new_values"]["expiry_date"] is None
    assert row["performed_by"]["id"] == user_a["id"]
    assert row["ip_address"], "la auditoría guarda la IP"



# ── Desde el portal (super_admin): /admin/tenants/{id}/batches ─────────────

@pytest.mark.asyncio
async def test_el_super_admin_lista_y_corrige_lotes_de_un_tenant(client, auth_headers_a, admin_auth_headers, env, super_admin_user):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))

    lista = await client.get(
        f"/admin/tenants/{env['tid']}/batches", params={"product_id": env["product"]}, headers=admin_auth_headers
    )
    assert lista.status_code == 200, lista.text
    (batch,) = [b for b in lista.json() if b["batch_number"] == "L-ERR"]

    resp = await client.patch(
        f"/admin/tenants/{env['tid']}/batches/{batch['id']}", json={"expiry_date": None}, headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["expiry_date"] is None
    assert await _balance_expiry(client, auth_headers_a, "L-ERR") is None

    (row,) = await _audit_rows(batch["id"], "UPDATE")
    assert row["performed_by"]["role"] == "super_admin"
    assert row["performed_by"]["id"] == super_admin_user["id"]


@pytest.mark.asyncio
async def test_el_super_admin_no_toca_un_lote_por_la_ruta_de_otro_tenant(
    client, auth_headers_a, admin_auth_headers, env, tenant_b
):
    await _receipt(client, auth_headers_a, env, "L-ERR", expiry=_in(1))
    batch = await _batch(client, auth_headers_a, env, "L-ERR")

    resp = await client.patch(
        f"/admin/tenants/{tenant_b['id']}/batches/{batch['id']}", json={"expiry_date": None}, headers=admin_auth_headers
    )
    assert resp.status_code == 404
    assert (await _batch(client, auth_headers_a, env, "L-ERR"))["expiry_date"] == _in(1)


@pytest.mark.asyncio
async def test_las_rutas_admin_de_lotes_rechazan_a_un_tenant_admin(client, auth_headers_a, env):
    assert (await client.get(f"/admin/tenants/{env['tid']}/batches", headers=auth_headers_a)).status_code == 403
