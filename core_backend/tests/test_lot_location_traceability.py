"""Trazabilidad de lotes y ubicaciones para Appits (migración 015).

1. Ubicación exacta (bin) en movimientos y saldos.
2. Proveedor en la entrada y en el lote (mismo número de lote de dos proveedores).
3. Lote en reservas y confirmaciones (FEFO/FIFO, reparto entre lotes, ledger por lote).
4. Filtros por lote y ubicación en saldos y ledger.
5. Lote obligatorio cuando el producto lo maneja.
6. Consecutivo de entrada (E-000058).
+ Compatibilidad: las llamadas actuales, sin campos nuevos, responden igual.
+ Aislamiento: bin, proveedor y lote de otro tenant se rechazan.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.services.reservation import _candidate_balances, expire_reservation
from tests.conftest import _TestSession, _create_product_simple, _create_warehouse, _create_zone, uid


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _bin(db, tenant_id: str, zone_id: str, code: str, active: bool = True) -> str:
    bid = uid()
    await db.execute(
        text(
            "INSERT INTO bins (id, tenant_id, zone_id, code, name, is_active, created_at, updated_at) "
            "VALUES (:id, :tid, :zid, :code, :name, :active, now(), now())"
        ),
        {"id": bid, "tid": tenant_id, "zid": zone_id, "code": code, "name": f"Estante {code}", "active": active},
    )
    await db.commit()
    return bid


async def _supplier(db, tenant_id: str, code: str) -> str:
    sid = uid()
    await db.execute(
        text(
            "INSERT INTO suppliers (id, tenant_id, code, name, currency, payment_terms_days, is_active, created_at, updated_at) "
            "VALUES (:id, :tid, :code, :name, 'COP', 30, true, now(), now())"
        ),
        {"id": sid, "tid": tenant_id, "code": code, "name": f"Proveedor {code}"},
    )
    await db.commit()
    return sid


async def _lot_product(db, tenant_id: str, sku: str) -> str:
    pid = uid()
    await db.execute(
        text(
            "INSERT INTO products (id, tenant_id, sku, name, base_uom, current_cpp, reorder_point, "
            "track_serials, track_lots, track_expiry, is_kit, is_active, low_stock_alert_enabled, created_at, updated_at) "
            "VALUES (:id, :tid, :sku, :name, 'UNIT', 0, 0, false, true, false, false, true, true, now(), now())"
        ),
        {"id": pid, "tid": tenant_id, "sku": sku, "name": f"Lote {sku}"},
    )
    await db.commit()
    return pid


async def _receipt(client, headers, env, items, supplier_id=None, zone=None, reference_id=None):
    body = {
        "reference_type": "PURCHASE_ORDER",
        "reference_id": reference_id or f"OC-{uid()[:6]}",
        "reason_code": "COMPRA",
        "warehouse_id": env["wh"],
        "zone_id": zone or env["zone"],
        "items": items,
    }
    if supplier_id:
        body["supplier_id"] = supplier_id
    return await client.post("/v1/transactions/receipts", json=body, headers=headers)


async def _reserve(client, headers, env, product_id, qty, reference_id=None, **extra):
    item = {"product_id": product_id, "warehouse_id": env["wh"], "zone_id": env["zone"], "quantity": qty, **extra}
    return await client.post(
        "/v1/reservations",
        json={"reference_type": "WORK_ORDER", "reference_id": reference_id or f"OT-{uid()[:6]}", "items": [item]},
        headers=headers,
    )


async def _balances(client, headers, **params):
    resp = await client.get("/v1/stock/balances", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _ledger(client, headers, **params):
    resp = await client.get("/v1/ledger", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _by_lot(balances):
    return {(b["lot_number"], b["supplier_id"]): b for b in balances}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def env(db, tenant_a):
    tid = tenant_a["id"]
    wh = await _create_warehouse(db, tid, f"WH-TR-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-TR-{uid()[:6]}")
    zone2 = await _create_zone(db, tid, wh["id"], f"Z2-TR-{uid()[:6]}")
    return {
        "tid": tid,
        "wh": wh["id"],
        "zone": zone["id"],
        "zone2": zone2["id"],
        "bin1": await _bin(db, tid, zone["id"], "E3-F1-N1"),
        "bin2": await _bin(db, tid, zone["id"], "E3-F1-N2"),
        "bin_other_zone": await _bin(db, tid, zone2["id"], "E9-F1-N1"),
        "sup_a": await _supplier(db, tid, f"PA-{uid()[:6]}"),
        "sup_b": await _supplier(db, tid, f"PB-{uid()[:6]}"),
        "plain": (await _create_product_simple(db, tid, f"PL-{uid()[:6]}"))["id"],
        "lot": await _lot_product(db, tid, f"LT-{uid()[:6]}"),
    }


@pytest_asyncio.fixture
async def env_b(db, tenant_b):
    tid = tenant_b["id"]
    wh = await _create_warehouse(db, tid, f"WH-TB-{uid()[:6]}")
    zone = await _create_zone(db, tid, wh["id"], f"Z-TB-{uid()[:6]}")
    return {
        "tid": tid,
        "wh": wh["id"],
        "zone": zone["id"],
        "bin": await _bin(db, tid, zone["id"], "B-OTRO"),
        "sup": await _supplier(db, tid, f"PX-{uid()[:6]}"),
        "lot": await _lot_product(db, tid, f"LB-{uid()[:6]}"),
    }


# ── Compatibilidad: llamadas actuales sin campos nuevos ────────────────────────

@pytest.mark.asyncio
async def test_compat_receipt_and_balances_without_new_fields(client, auth_headers_a, env):
    resp = await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 10, "unit_cost": 100}])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert {"transaction_id", "transaction_type", "timestamp", "status", "items_processed"} <= body.keys()
    assert body["transaction_type"] == "RECEIPT"

    [bal] = await _balances(client, auth_headers_a, product_id=env["plain"])
    for field in ("id", "product_id", "warehouse_id", "zone_id", "lot_number", "physical_qty", "reserved_qty", "available_qty"):
        assert field in bal
    assert float(bal["physical_qty"]) == 10.0
    assert bal["bin_id"] is None and bal["supplier_id"] is None


@pytest.mark.asyncio
async def test_compat_reservation_confirm_cancel_without_new_fields(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 20, "unit_cost": 100}])

    resp = await _reserve(client, auth_headers_a, env, env["plain"], 4)
    assert resp.status_code == 201, resp.text
    item = resp.json()["items"][0]
    for field in ("id", "product_id", "warehouse_id", "zone_id", "quantity", "confirmed_qty"):
        assert field in item
    assert [float(a["quantity"]) for a in item["allocations"]] == [4.0]

    confirm = await client.post(
        f"/v1/reservations/{resp.json()['id']}/confirm",
        json={"actual_quantity_to_issue": 4, "issue_reference": "INV-1"},
        headers=auth_headers_a,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "COMPLETED"

    other = await _reserve(client, auth_headers_a, env, env["plain"], 5)
    cancel = await client.post(f"/v1/reservations/{other.json()['id']}/cancel", headers=auth_headers_a)
    assert cancel.status_code == 200

    [bal] = await _balances(client, auth_headers_a, product_id=env["plain"])
    assert float(bal["physical_qty"]) == 16.0
    assert float(bal["reserved_qty"]) == 0.0
    assert float(bal["available_qty"]) == 16.0


@pytest.mark.asyncio
async def test_compat_legacy_reservation_without_allocations(client, auth_headers_a, db, env):
    """Una reserva creada antes de la 015 (sin asignaciones) se confirma contra el saldo de la zona."""
    await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 10, "unit_cost": 100}])
    [bal] = await _balances(client, auth_headers_a, product_id=env["plain"])
    await db.execute(
        text("UPDATE stock_balances SET reserved_qty = 3, available_qty = 7 WHERE id = :id"), {"id": bal["id"]}
    )
    rid, iid = uid(), uid()
    await db.execute(
        text(
            "INSERT INTO reservations (id, tenant_id, reference_type, reference_id, status, expires_at, created_at, updated_at) "
            "VALUES (:id, :tid, 'WORK_ORDER', 'OT-LEGACY', 'ACTIVE', now() + interval '1 hour', now(), now())"
        ),
        {"id": rid, "tid": env["tid"]},
    )
    await db.execute(
        text(
            "INSERT INTO reservation_items (id, reservation_id, tenant_id, product_id, warehouse_id, zone_id, quantity, confirmed_qty) "
            "VALUES (:id, :rid, :tid, :pid, :wid, :zid, 3, 0)"
        ),
        {"id": iid, "rid": rid, "tid": env["tid"], "pid": env["plain"], "wid": env["wh"], "zid": env["zone"]},
    )
    await db.commit()

    resp = await client.post(
        f"/v1/reservations/{rid}/confirm",
        json={"actual_quantity_to_issue": 3, "issue_reference": "INV-LEG"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["allocations"] == []

    [bal] = await _balances(client, auth_headers_a, product_id=env["plain"])
    assert float(bal["physical_qty"]) == 7.0
    assert float(bal["reserved_qty"]) == 0.0


@pytest.mark.asyncio
async def test_ledger_accepts_legacy_rows_without_transaction(client, auth_headers_a, db, env):
    """Antes de la 015 las confirmaciones escribían el ledger sin transaction_id y GET /v1/ledger daba 500."""
    await db.execute(
        text(
            "INSERT INTO inventory_ledger (id, tenant_id, product_id, warehouse_id, zone_id, movement_type, qty_change, "
            "reference_type, reference_id, reason_code, created_at) "
            "VALUES (:id, :tid, :pid, :wid, :zid, 'ISSUE', -1, 'RESERVATION_CONFIRM', 'INV-OLD', 'RESERVATION', now())"
        ),
        {"id": uid(), "tid": env["tid"], "pid": env["plain"], "wid": env["wh"], "zid": env["zone"]},
    )
    await db.commit()
    entries = await _ledger(client, auth_headers_a, product_id=env["plain"])
    assert entries[0]["transaction_id"] is None


# ── 1. Ubicación exacta (bin) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receipt_into_bin_keeps_separate_balance(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 5}])
    resp = await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 7, "bin_id": env["bin1"]}])
    assert resp.status_code == 201, resp.text

    balances = await _balances(client, auth_headers_a, product_id=env["plain"])
    by_bin = {b["bin_id"]: b for b in balances}
    assert float(by_bin[None]["physical_qty"]) == 5.0
    assert float(by_bin[env["bin1"]]["physical_qty"]) == 7.0
    assert by_bin[env["bin1"]]["bin_code"] == "E3-F1-N1"
    assert by_bin[env["bin1"]]["bin_name"] == "Estante E3-F1-N1"


@pytest.mark.asyncio
async def test_bin_must_belong_to_zone_and_be_active(client, auth_headers_a, db, env):
    wrong_zone = await _receipt(
        client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 1, "bin_id": env["bin_other_zone"]}]
    )
    assert wrong_zone.status_code == 422
    assert "no pertenece a la zona" in wrong_zone.json()["detail"]

    inactive = await _bin(db, env["tid"], env["zone"], "INACTIVO", active=False)
    resp = await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 1, "bin_id": inactive}])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_issue_adjust_and_transfer_by_bin(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 10, "bin_id": env["bin1"]}])

    issue = await client.post(
        "/v1/transactions/issues",
        json={
            "reference_type": "WORK_ORDER", "reference_id": "OT-1", "reason_code": "CONSUMO_TALLER",
            "warehouse_id": env["wh"], "zone_id": env["zone"],
            "items": [{"product_id": env["plain"], "quantity": 2, "bin_id": env["bin1"]}],
        },
        headers=auth_headers_a,
    )
    assert issue.status_code == 201, issue.text

    transfer = await client.post(
        "/v1/transactions/transfers",
        json={
            "reference_id": "TRF-1",
            "source_warehouse_id": env["wh"], "source_zone_id": env["zone"],
            "target_warehouse_id": env["wh"], "target_zone_id": env["zone"],
            "items": [{"product_id": env["plain"], "quantity": 3, "from_bin_id": env["bin1"], "to_bin_id": env["bin2"]}],
        },
        headers=auth_headers_a,
    )
    assert transfer.status_code == 201, transfer.text

    adjust = await client.post(
        "/v1/transactions/adjustments",
        json={
            "reference_id": "CONTEO-1", "warehouse_id": env["wh"], "zone_id": env["zone"],
            "items": [{"product_id": env["plain"], "new_qty": 4, "bin_id": env["bin2"]}],
        },
        headers=auth_headers_a,
    )
    assert adjust.status_code == 201, adjust.text

    by_bin = {b["bin_id"]: b for b in await _balances(client, auth_headers_a, product_id=env["plain"])}
    assert float(by_bin[env["bin1"]]["physical_qty"]) == 5.0   # 10 − 2 − 3
    assert float(by_bin[env["bin2"]]["physical_qty"]) == 4.0   # 3 → ajustado a 4

    moves = {(e["movement_type"], e["bin_id"]) for e in await _ledger(client, auth_headers_a, product_id=env["plain"])}
    assert ("ISSUE", env["bin1"]) in moves
    assert ("TRANSFER_OUT", env["bin1"]) in moves
    assert ("TRANSFER_IN", env["bin2"]) in moves
    assert ("ADJUSTMENT", env["bin2"]) in moves


@pytest.mark.asyncio
async def test_transfer_bins_validated_against_their_zones(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 5, "bin_id": env["bin1"]}])
    resp = await client.post(
        "/v1/transactions/transfers",
        json={
            "reference_id": "TRF-2",
            "source_warehouse_id": env["wh"], "source_zone_id": env["zone"],
            "target_warehouse_id": env["wh"], "target_zone_id": env["zone2"],
            "items": [{"product_id": env["plain"], "quantity": 1, "from_bin_id": env["bin1"], "to_bin_id": env["bin2"]}],
        },
        headers=auth_headers_a,
    )
    assert resp.status_code == 422  # bin2 es de la zona origen, no de la destino


# ── 2. Proveedor en la entrada y en el lote ───────────────────────────────────

@pytest.mark.asyncio
async def test_same_lot_number_from_two_suppliers_stays_separate(client, auth_headers_a, env):
    """20 del proveedor A y 20 del B, ambos con el lote L-100: dos lotes, dos saldos."""
    for sup in (env["sup_a"], env["sup_b"]):
        resp = await _receipt(
            client, auth_headers_a, env,
            [{"product_id": env["lot"], "quantity": 20, "lot_number": "L-100", "unit_cost": 50}],
            supplier_id=sup,
        )
        assert resp.status_code == 201, resp.text

    balances = _by_lot(await _balances(client, auth_headers_a, product_id=env["lot"]))
    assert float(balances[("L-100", env["sup_a"])]["physical_qty"]) == 20.0
    assert float(balances[("L-100", env["sup_b"])]["physical_qty"]) == 20.0

    batches = (await client.get(f"/v1/batches?product_id={env['lot']}", headers=auth_headers_a)).json()
    assert {(b["batch_number"], b["supplier_id"]) for b in batches} == {("L-100", env["sup_a"]), ("L-100", env["sup_b"])}

    # Una salida de L-100 sin proveedor es ambigua; con proveedor sale de ese lote.
    issue = {
        "reference_type": "WORK_ORDER", "reference_id": "OT-2", "reason_code": "CONSUMO_TALLER",
        "warehouse_id": env["wh"], "zone_id": env["zone"],
        "items": [{"product_id": env["lot"], "quantity": 5, "lot_number": "L-100"}],
    }
    ambiguous = await client.post("/v1/transactions/issues", json=issue, headers=auth_headers_a)
    assert ambiguous.status_code == 409
    assert "supplier_id" in ambiguous.json()["detail"]

    issue["items"][0]["supplier_id"] = env["sup_b"]
    ok = await client.post("/v1/transactions/issues", json=issue, headers=auth_headers_a)
    assert ok.status_code == 201, ok.text
    balances = _by_lot(await _balances(client, auth_headers_a, product_id=env["lot"]))
    assert float(balances[("L-100", env["sup_b"])]["physical_qty"]) == 15.0
    assert float(balances[("L-100", env["sup_a"])]["physical_qty"]) == 20.0


@pytest.mark.asyncio
async def test_receipt_creates_batch_inheriting_supplier_and_expiry(client, auth_headers_a, env):
    resp = await _receipt(
        client, auth_headers_a, env,
        [{"product_id": env["lot"], "quantity": 12, "lot_number": "L-EXP", "expiry_date": "2027-03-31"}],
        supplier_id=env["sup_a"],
    )
    assert resp.status_code == 201, resp.text
    [batch] = (await client.get(f"/v1/batches?product_id={env['lot']}", headers=auth_headers_a)).json()
    assert batch["batch_number"] == "L-EXP"
    assert batch["supplier_id"] == env["sup_a"]
    assert batch["expiry_date"] == "2027-03-31"
    assert float(batch["initial_qty"]) == 12.0


@pytest.mark.asyncio
async def test_batch_number_unique_per_product_and_supplier(client, auth_headers_a, env):
    async def create(supplier_id):
        payload = {"product_id": env["lot"], "batch_number": "L-DUP", "initial_qty": 5}
        if supplier_id:
            payload["supplier_id"] = supplier_id
        return await client.post("/v1/batches", json=payload, headers=auth_headers_a)

    first = await create(env["sup_a"])
    assert first.status_code == 201, first.text
    assert first.json()["supplier_id"] == env["sup_a"]
    assert (await create(env["sup_a"])).status_code == 409
    assert (await create(env["sup_b"])).status_code == 201
    assert (await create(None)).status_code == 201


# ── 3. Lote en reservas y confirmaciones ──────────────────────────────────────

async def _two_lots(client, headers, env, late_qty=5, early_qty=5):
    """L-LATE (vence 2027-12-31) entra primero; L-EARLY (vence 2027-01-31) después."""
    await _receipt(client, headers, env, [{"product_id": env["lot"], "quantity": late_qty, "lot_number": "L-LATE",
                                           "expiry_date": "2027-12-31", "bin_id": env["bin2"]}], supplier_id=env["sup_a"])
    await _receipt(client, headers, env, [{"product_id": env["lot"], "quantity": early_qty, "lot_number": "L-EARLY",
                                           "expiry_date": "2027-01-31", "bin_id": env["bin1"]}], supplier_id=env["sup_b"])


@pytest.mark.asyncio
async def test_reservation_picks_first_expiring_lot_fefo(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)
    resp = await _reserve(client, auth_headers_a, env, env["lot"], 3)
    assert resp.status_code == 201, resp.text
    [alloc] = resp.json()["items"][0]["allocations"]
    assert alloc["lot_number"] == "L-EARLY"
    assert alloc["bin_id"] == env["bin1"]
    assert alloc["bin_code"] == "E3-F1-N1"
    assert alloc["supplier_id"] == env["sup_b"]
    assert alloc["expiry_date"] == "2027-01-31"
    assert float(alloc["quantity"]) == 3.0


@pytest.mark.asyncio
async def test_reservation_without_expiry_uses_fifo(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["lot"], "quantity": 5, "lot_number": "L-FIRST"}])
    await _receipt(client, auth_headers_a, env, [{"product_id": env["lot"], "quantity": 5, "lot_number": "L-SECOND"}])
    resp = await _reserve(client, auth_headers_a, env, env["lot"], 2)
    assert resp.status_code == 201, resp.text
    assert [a["lot_number"] for a in resp.json()["items"][0]["allocations"]] == ["L-FIRST"]


@pytest.mark.asyncio
async def test_reservation_splits_across_lots(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)
    resp = await _reserve(client, auth_headers_a, env, env["lot"], 8)
    assert resp.status_code == 201, resp.text
    allocs = [(a["lot_number"], float(a["quantity"])) for a in resp.json()["items"][0]["allocations"]]
    assert allocs == [("L-EARLY", 5.0), ("L-LATE", 3.0)]

    balances = _by_lot(await _balances(client, auth_headers_a, product_id=env["lot"]))
    assert float(balances[("L-EARLY", env["sup_b"])]["available_qty"]) == 0.0
    assert float(balances[("L-LATE", env["sup_a"])]["reserved_qty"]) == 3.0
    assert float(balances[("L-LATE", env["sup_a"])]["available_qty"]) == 2.0


@pytest.mark.asyncio
async def test_reservation_with_explicit_lot_and_bin(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)
    resp = await _reserve(client, auth_headers_a, env, env["lot"], 2, lot_number="L-LATE", bin_id=env["bin2"])
    assert resp.status_code == 201, resp.text
    item = resp.json()["items"][0]
    assert item["lot_number"] == "L-LATE" and item["bin_id"] == env["bin2"]
    assert [a["lot_number"] for a in item["allocations"]] == ["L-LATE"]

    too_much = await _reserve(client, auth_headers_a, env, env["lot"], 6, lot_number="L-LATE")
    assert too_much.status_code == 409


@pytest.mark.asyncio
async def test_confirm_issues_per_lot_with_order_reference(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)
    order = f"OT-{uid()[:6]}"
    res = await _reserve(client, auth_headers_a, env, env["lot"], 8, reference_id=order)
    confirm = await client.post(
        f"/v1/reservations/{res.json()['id']}/confirm",
        json={"actual_quantity_to_issue": 8, "issue_reference": "FACT-77"},
        headers=auth_headers_a,
    )
    assert confirm.status_code == 200, confirm.text
    allocs = [(a["lot_number"], float(a["confirmed_qty"])) for a in confirm.json()["items"][0]["allocations"]]
    assert allocs == [("L-EARLY", 5.0), ("L-LATE", 3.0)]

    issues = await _ledger(client, auth_headers_a, reference_id=order)
    got = {(e["lot_number"], e["bin_id"], e["supplier_id"], float(e["qty_change"])) for e in issues}
    assert got == {("L-EARLY", env["bin1"], env["sup_b"], -5.0), ("L-LATE", env["bin2"], env["sup_a"], -3.0)}
    assert all(e["movement_type"] == "ISSUE" and e["transaction_id"] for e in issues)

    # "¿En qué órdenes se usó el lote L-EARLY?"
    used = await _ledger(client, auth_headers_a, lot_number="L-EARLY", product_id=env["lot"])
    assert order in {e["reference_id"] for e in used if e["movement_type"] == "ISSUE"}


@pytest.mark.asyncio
async def test_partial_confirm_consumes_in_fefo_order_and_releases_rest(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)
    res = await _reserve(client, auth_headers_a, env, env["lot"], 8)
    confirm = await client.post(
        f"/v1/reservations/{res.json()['id']}/confirm",
        json={"actual_quantity_to_issue": 6, "issue_reference": "FACT-78"},
        headers=auth_headers_a,
    )
    assert confirm.status_code == 200, confirm.text

    balances = _by_lot(await _balances(client, auth_headers_a, product_id=env["lot"]))
    early, late = balances[("L-EARLY", env["sup_b"])], balances[("L-LATE", env["sup_a"])]
    assert float(early["physical_qty"]) == 0.0
    assert (float(late["physical_qty"]), float(late["reserved_qty"]), float(late["available_qty"])) == (4.0, 0.0, 4.0)


@pytest.mark.asyncio
async def test_reservation_locks_the_balances_it_allocates(client, auth_headers_a, env):
    """Mientras una reserva reparte, sus saldos candidatos quedan bloqueados hasta el commit.

    Es lo que impide que dos reservas simultáneas aparten las mismas unidades. Se prueba
    de forma determinista: la sesión 1 toma los saldos y no confirma; la sesión 2 no
    puede tomarlos (lock_timeout) en vez de leer un disponible que ya no es real.
    """
    await _receipt(client, auth_headers_a, env, [{"product_id": env["lot"], "quantity": 5, "lot_number": "L-RACE"}])
    item = SimpleNamespace(product_id=env["lot"], zone_id=env["zone"], lot_number=None, bin_id=None, supplier_id=None)

    async with _TestSession() as first, _TestSession() as second:
        assert await _candidate_balances(first, env["tid"], item, True)
        await second.execute(text("SET LOCAL lock_timeout = '300ms'"))
        with pytest.raises(DBAPIError):
            await _candidate_balances(second, env["tid"], item, True)
        await second.rollback()
        await first.rollback()


@pytest.mark.asyncio
async def test_confirm_more_than_reserved_is_rejected(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 10}])
    res = await _reserve(client, auth_headers_a, env, env["plain"], 2)
    resp = await client.post(
        f"/v1/reservations/{res.json()['id']}/confirm",
        json={"actual_quantity_to_issue": 3, "issue_reference": "X"},
        headers=auth_headers_a,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cancel_and_expire_release_every_lot(client, auth_headers_a, db, env):
    await _two_lots(client, auth_headers_a, env)

    res = await _reserve(client, auth_headers_a, env, env["lot"], 8)
    assert (await client.post(f"/v1/reservations/{res.json()['id']}/cancel", headers=auth_headers_a)).status_code == 200

    res = await _reserve(client, auth_headers_a, env, env["lot"], 7)
    await expire_reservation(db, env["tid"], res.json()["id"])
    await db.commit()
    assert (await client.get(f"/v1/reservations/{res.json()['id']}", headers=auth_headers_a)).json()["status"] == "EXPIRED"

    for bal in await _balances(client, auth_headers_a, product_id=env["lot"]):
        assert float(bal["reserved_qty"]) == 0.0
        assert float(bal["available_qty"]) == float(bal["physical_qty"]) == 5.0


# ── 4. Filtros por lote y ubicación ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_balance_filters_by_lot_bin_and_supplier(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)

    [where] = await _balances(client, auth_headers_a, lot_number="L-EARLY")
    assert (where["zone_id"], where["bin_id"], where["supplier_id"]) == (env["zone"], env["bin1"], env["sup_b"])
    assert where["expiry_date"] == "2027-01-31"

    shelf = await _balances(client, auth_headers_a, bin_id=env["bin2"])
    assert [b["lot_number"] for b in shelf] == ["L-LATE"]

    from_a = await _balances(client, auth_headers_a, supplier_id=env["sup_a"])
    assert [b["lot_number"] for b in from_a] == ["L-LATE"]


@pytest.mark.asyncio
async def test_ledger_filters_and_fields(client, auth_headers_a, env):
    await _two_lots(client, auth_headers_a, env)
    today = datetime.now(timezone.utc).date()

    [entry] = await _ledger(client, auth_headers_a, lot_number="L-LATE")
    assert (entry["bin_id"], entry["bin_code"], entry["supplier_id"]) == (env["bin2"], "E3-F1-N2", env["sup_a"])
    assert entry["expiry_date"] == "2027-12-31"

    assert len(await _ledger(client, auth_headers_a, zone_id=env["zone"], product_id=env["lot"])) == 2
    assert len(await _ledger(client, auth_headers_a, bin_id=env["bin1"])) == 1
    assert len(await _ledger(client, auth_headers_a, supplier_id=env["sup_b"])) == 1
    assert len(await _ledger(client, auth_headers_a, product_id=env["lot"], date_from=str(today), date_to=str(today))) == 2
    yesterday = str(today - timedelta(days=1))
    assert await _ledger(client, auth_headers_a, product_id=env["lot"], date_to=yesterday) == []


# ── 5. Lote obligatorio con track_lots ────────────────────────────────────────

@pytest.mark.asyncio
async def test_track_lots_requires_lot_on_receipt_adjustment_and_transfer(client, auth_headers_a, env):
    receipt = await _receipt(client, auth_headers_a, env, [{"product_id": env["lot"], "quantity": 1}])
    assert receipt.status_code == 422
    assert "maneja lotes" in receipt.json()["detail"]

    adjust = await client.post(
        "/v1/transactions/adjustments",
        json={"reference_id": "C-1", "warehouse_id": env["wh"], "zone_id": env["zone"],
              "items": [{"product_id": env["lot"], "new_qty": 3}]},
        headers=auth_headers_a,
    )
    assert adjust.status_code == 422

    transfer = await client.post(
        "/v1/transactions/transfers",
        json={"reference_id": "T-1", "source_warehouse_id": env["wh"], "source_zone_id": env["zone"],
              "target_warehouse_id": env["wh"], "target_zone_id": env["zone2"],
              "items": [{"product_id": env["lot"], "quantity": 1}]},
        headers=auth_headers_a,
    )
    assert transfer.status_code == 422


@pytest.mark.asyncio
async def test_reservation_without_lot_is_not_rejected_for_lot_product(client, auth_headers_a, env):
    await _receipt(client, auth_headers_a, env, [{"product_id": env["lot"], "quantity": 4, "lot_number": "L-OK"}])
    resp = await _reserve(client, auth_headers_a, env, env["lot"], 2)
    assert resp.status_code == 201, resp.text
    assert resp.json()["items"][0]["allocations"][0]["lot_number"] == "L-OK"


# ── 6. Consecutivo de entrada ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receipt_document_number_is_consecutive_and_searchable(client, auth_headers_a, env):
    first = (await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 1}])).json()
    second = (await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 1}])).json()

    n1, n2 = first["document_number"], second["document_number"]
    assert n1.startswith("E-") and len(n1) == 8
    assert int(n2[2:]) == int(n1[2:]) + 1

    [entry] = await _ledger(client, auth_headers_a, document_number=n2)
    assert entry["transaction_id"] == second["transaction_id"]
    assert entry["document_number"] == n2


# ── Panel admin: proveedores para nombrar el proveedor de cada lote ──────────

@pytest.mark.asyncio
async def test_admin_lists_all_suppliers_of_a_tenant(client, admin_auth_headers, db, env, env_b):
    await db.execute(text("UPDATE suppliers SET is_active = false WHERE id = :id"), {"id": env["sup_b"]})
    await db.commit()

    resp = await client.get(f"/admin/tenants/{env['tid']}/suppliers", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    ids = {s["id"] for s in resp.json()}
    assert {env["sup_a"], env["sup_b"]} <= ids   # incluye el inactivo
    assert env_b["sup"] not in ids                # y nada de otro tenant


# ── Aislamiento entre tenants ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bin_supplier_and_lot_of_another_tenant_are_rejected(client, auth_headers_a, auth_headers_b, env, env_b):
    # B tiene stock del lote L-B en su bin, de su proveedor.
    resp = await _receipt(
        client, auth_headers_b, env_b,
        [{"product_id": env_b["lot"], "quantity": 5, "lot_number": "L-B", "bin_id": env_b["bin"]}],
        supplier_id=env_b["sup"],
    )
    assert resp.status_code == 201, resp.text

    # A no puede usar el bin ni el proveedor de B.
    foreign_bin = await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 1, "bin_id": env_b["bin"]}])
    assert foreign_bin.status_code == 404
    foreign_supplier = await _receipt(client, auth_headers_a, env, [{"product_id": env["plain"], "quantity": 1}],
                                      supplier_id=env_b["sup"])
    assert foreign_supplier.status_code == 404
    foreign_batch = await client.post(
        "/v1/batches",
        json={"product_id": env["lot"], "batch_number": "L-X", "initial_qty": 1, "supplier_id": env_b["sup"]},
        headers=auth_headers_a,
    )
    assert foreign_batch.status_code == 404
    foreign_res_bin = await _reserve(client, auth_headers_a, env, env["plain"], 1, bin_id=env_b["bin"])
    assert foreign_res_bin.status_code == 404

    # Ni reservar ni ver el lote de B.
    foreign_lot = await _reserve(client, auth_headers_a, env, env["lot"], 1, lot_number="L-B")
    assert foreign_lot.status_code == 409
    assert await _balances(client, auth_headers_a, lot_number="L-B") == []
    assert await _balances(client, auth_headers_a, bin_id=env_b["bin"]) == []
    assert await _ledger(client, auth_headers_a, lot_number="L-B") == []
