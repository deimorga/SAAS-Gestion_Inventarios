"""
Revisión 2026-11-19 — R-05 y R-09 (movimientos de inventario).

R-05: `require_lot` bloqueaba ajustes y traslados de un saldo histórico SIN lote de un producto que hoy
      maneja lotes (p. ej. «Poner en 0» desde el portal): ese stock no se podía corregir.
R-09: una salida con varios ítems del mismo saldo validaba cada uno contra `available_qty` por separado,
      sin restar los anteriores, y terminaba consumiendo stock RESERVADO.

Las pruebas solo tocan datos que crean ellas mismas (L-4).
"""
import pytest
import pytest_asyncio
from sqlalchemy import text

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
    wh = await _create_warehouse(db, tid, f"WH-RI-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-RI-{uid()[:6]}")
    zone2 = await _create_zone(db, tid, wh["id"], f"Z2-RI-{uid()[:6]}")
    return {
        "tid": tid, "wh": wh["id"], "zone": zone["id"], "zone2": zone2["id"],
        "plain": await _product(db, tid, track_lots=False),
        "plain_2": await _product(db, tid, track_lots=False),
        "lots": await _product(db, tid, track_lots=True),
    }


async def _historic_balance(env, product_id: str, *, physical: int, reserved: int = 0, zone: str | None = None) -> str:
    """Saldo sin lote, como los que existen de antes de que el producto manejara lotes."""
    bid = uid()
    async with _TestSession() as s:
        await s.execute(
            text(
                "INSERT INTO stock_balances (id, tenant_id, product_id, warehouse_id, zone_id, lot_number, "
                " physical_qty, reserved_qty, available_qty) "
                "VALUES (:id, :tid, :pid, :wid, :zid, NULL, :phys, :res, :avail)"
            ),
            {"id": bid, "tid": env["tid"], "pid": product_id, "wid": env["wh"], "zid": zone or env["zone"],
             "phys": physical, "res": reserved, "avail": physical - reserved},
        )
        await s.commit()
    return bid


async def _balance(balance_id: str) -> dict:
    async with _TestSession() as s:
        row = (
            await s.execute(
                text("SELECT physical_qty, reserved_qty, available_qty FROM stock_balances WHERE id = :id"),
                {"id": balance_id},
            )
        ).mappings().one()
    return {k: float(v) for k, v in row.items()}


async def _balances_of(product_id: str, zone_id: str) -> list[dict]:
    async with _TestSession() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT lot_number, physical_qty FROM stock_balances WHERE product_id = :pid AND zone_id = :zid"
                ),
                {"pid": product_id, "zid": zone_id},
            )
        ).mappings().all()
    return [{"lot_number": r["lot_number"], "physical_qty": float(r["physical_qty"])} for r in rows]


async def _adjust(client, headers, env, product_id: str, new_qty: int, lot: str | None = None):
    item = {"product_id": product_id, "new_qty": new_qty}
    if lot:
        item["lot_number"] = lot
    return await client.post(
        "/v1/transactions/adjustments",
        json={"reference_id": f"AJ-{uid()[:6]}", "reason_code": "CONTEO_FISICO",
              "warehouse_id": env["wh"], "zone_id": env["zone"], "items": [item]},
        headers=headers,
    )


async def _transfer(client, headers, env, items: list[dict]):
    return await client.post(
        "/v1/transactions/transfers",
        json={"reference_id": f"TR-{uid()[:6]}", "source_warehouse_id": env["wh"], "source_zone_id": env["zone"],
              "target_warehouse_id": env["wh"], "target_zone_id": env["zone2"], "items": items},
        headers=headers,
    )


async def _issue(client, headers, env, items: list[dict]):
    return await client.post(
        "/v1/transactions/issues",
        json={"reference_type": "SALES_ORDER", "reference_id": f"SO-{uid()[:6]}", "reason_code": "VENTA_CLIENTE",
              "warehouse_id": env["wh"], "zone_id": env["zone"], "items": items},
        headers=headers,
    )


# ── R-05: el stock histórico sin lote se puede corregir y trasladar ────────

@pytest.mark.asyncio
async def test_r05_poner_en_cero_un_saldo_historico_sin_lote(client, auth_headers_a, env):
    bid = await _historic_balance(env, env["lots"], physical=7)
    resp = await _adjust(client, auth_headers_a, env, env["lots"], 0)
    assert resp.status_code == 201, resp.text
    assert (await _balance(bid))["physical_qty"] == 0


@pytest.mark.asyncio
async def test_r05_trasladar_un_saldo_historico_sin_lote(client, auth_headers_a, env):
    bid = await _historic_balance(env, env["lots"], physical=7)
    resp = await _transfer(client, auth_headers_a, env, [{"product_id": env["lots"], "quantity": 3}])
    assert resp.status_code == 201, resp.text
    assert (await _balance(bid))["physical_qty"] == 4
    assert await _balances_of(env["lots"], env["zone2"]) == [{"lot_number": None, "physical_qty": 3.0}]


@pytest.mark.asyncio
async def test_r05_sin_lote_y_sin_saldo_existente_sigue_exigiendo_lote(client, auth_headers_a, env):
    """El lote solo deja de exigirse para corregir lo que ya existe: un saldo NUEVO sin lote no se crea."""
    ajuste = await _adjust(client, auth_headers_a, env, env["lots"], 5)
    assert ajuste.status_code == 422, ajuste.text
    assert "lot_number" in ajuste.json()["detail"]
    traslado = await _transfer(client, auth_headers_a, env, [{"product_id": env["lots"], "quantity": 1}])
    assert traslado.status_code == 422, traslado.text
    assert await _balances_of(env["lots"], env["zone"]) == []
    assert await _balances_of(env["lots"], env["zone2"]) == []


@pytest.mark.asyncio
async def test_r05_con_lote_indicado_el_ajuste_funciona_como_siempre(client, auth_headers_a, env):
    resp = await _adjust(client, auth_headers_a, env, env["lots"], 4, lot="L-REV-1")
    assert resp.status_code == 201, resp.text
    assert await _balances_of(env["lots"], env["zone"]) == [{"lot_number": "L-REV-1", "physical_qty": 4.0}]


# ── R-09: una salida no consume stock reservado ────────────────────────────

@pytest.mark.asyncio
async def test_r09_dos_items_del_mismo_saldo_no_consumen_lo_reservado(client, auth_headers_a, env):
    bid = await _historic_balance(env, env["plain"], physical=10, reserved=6)  # disponible: 4
    resp = await _issue(client, auth_headers_a, env, [
        {"product_id": env["plain"], "quantity": 3},
        {"product_id": env["plain"], "quantity": 3},
    ])
    assert resp.status_code == 409, resp.text
    assert "Stock insuficiente" in resp.json()["detail"]
    assert await _balance(bid) == {"physical_qty": 10.0, "reserved_qty": 6.0, "available_qty": 4.0}


@pytest.mark.asyncio
async def test_r09_lo_justo_para_el_disponible_si_se_despacha(client, auth_headers_a, env):
    bid = await _historic_balance(env, env["plain"], physical=10, reserved=6)
    resp = await _issue(client, auth_headers_a, env, [
        {"product_id": env["plain"], "quantity": 3},
        {"product_id": env["plain"], "quantity": 1},
    ])
    assert resp.status_code == 201, resp.text
    assert await _balance(bid) == {"physical_qty": 6.0, "reserved_qty": 6.0, "available_qty": 0.0}


@pytest.mark.asyncio
async def test_r09_items_de_saldos_distintos_no_se_suman_entre_si(client, auth_headers_a, env):
    a = await _historic_balance(env, env["plain"], physical=10, reserved=6)  # disponible 4
    b = await _historic_balance(env, env["plain_2"], physical=10, reserved=0)  # disponible 10
    resp = await _issue(client, auth_headers_a, env, [
        {"product_id": env["plain"], "quantity": 4},
        {"product_id": env["plain_2"], "quantity": 9},
    ])
    assert resp.status_code == 201, resp.text
    assert (await _balance(a))["physical_qty"] == 6
    assert (await _balance(b))["physical_qty"] == 1


@pytest.mark.asyncio
async def test_r09_dos_items_del_mismo_saldo_en_un_traslado_tampoco_consumen_lo_reservado(client, auth_headers_a, env):
    bid = await _historic_balance(env, env["plain"], physical=10, reserved=6)
    resp = await _transfer(client, auth_headers_a, env, [
        {"product_id": env["plain"], "quantity": 3},
        {"product_id": env["plain"], "quantity": 3},
    ])
    assert resp.status_code == 409, resp.text
    assert await _balance(bid) == {"physical_qty": 10.0, "reserved_qty": 6.0, "available_qty": 4.0}
    assert await _balances_of(env["plain"], env["zone2"]) == []


@pytest.mark.asyncio
async def test_r09_un_reempaque_tampoco_consume_lo_reservado(client, auth_headers_a, env):
    bid = await _historic_balance(env, env["plain"], physical=10, reserved=6)  # disponible: 4
    resp = await client.post(
        "/v1/transactions/repacks",
        json={
            "reference_id": f"RP-{uid()[:6]}", "warehouse_id": env["wh"], "zone_id": env["zone"],
            "source_items": [
                {"product_id": env["plain"], "quantity": 3},
                {"product_id": env["plain"], "quantity": 3},
            ],
            "target_items": [{"product_id": env["plain_2"], "quantity": 1}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 409, resp.text
    assert await _balance(bid) == {"physical_qty": 10.0, "reserved_qty": 6.0, "available_qty": 4.0}
    assert await _balances_of(env["plain_2"], env["zone"]) == [], "no se generó nada del destino"
