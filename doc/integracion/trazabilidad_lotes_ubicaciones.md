# Lotes, proveedores y ubicaciones exactas — contrato para Appits

> Última actualización: 2026-11-04 · Estado: **implementado (migración 015)**, pendiente de commit, merge y despliegue.

Inventarios ahora sabe **dónde** está cada repuesto (bodega → zona → ubicación/bin), **de qué
proveedor** vino cada lote y **en qué orden de servicio** se consumió.

**Compatibilidad:** todo campo nuevo es **opcional**. Ningún campo existente cambió de nombre
ni de tipo, y las respuestas conservan todos sus campos (solo se agregan). Las llamadas
actuales de Appits, sin campos nuevos, se comportan igual. Hay tres excepciones, todas
listadas en [Cambios de comportamiento](#cambios-de-comportamiento-que-appits-debe-conocer).

---

## Conceptos

| Concepto | Qué es |
|---|---|
| **Bin** | Ubicación exacta dentro de una zona (estante, fila, nivel). Se crean con `POST /v1/warehouses/{wid}/zones/{zid}/bins` y se listan con `GET` en la misma ruta. |
| **Lote** | Producto + **proveedor** + número de lote. El mismo número `L-100` traído por dos proveedores son **dos lotes distintos**, con saldos separados. |
| **Saldo** | Se lleva por producto + zona + bin + lote + proveedor. El stock que ya existía queda con bin y proveedor en `null`. |
| **Stock sin ubicar** | Lo que entra sin `bin_id`. Una salida sin `bin_id` sale de ahí; una **reserva** sin `bin_id` busca en toda la zona. |

---

## 1. Entrada — `POST /v1/transactions/receipts`

**Entrada nueva (opcional)**

| Campo | Dónde | Descripción |
|---|---|---|
| `supplier_id` | cabecera | Proveedor de la mercancía; debe ser del tenant. |
| `items[].bin_id` | ítem | Bin destino; debe pertenecer a `zone_id`. |
| `items[].supplier_id` | ítem | Sobrescribe el de la cabecera para ese ítem. |

**Respuesta nueva:** `document_number` (consecutivo por tenant, ej. `E-000058`).

**Efectos:** si el producto tiene `track_lots = true` y el ítem trae `lot_number`, la entrada
**crea el lote** (o reutiliza el existente) heredando `supplier_id` y `expiry_date`.

```json
// REQUEST
{
  "reference_type": "PURCHASE_ORDER", "reference_id": "OC-2026-00146", "reason_code": "COMPRA",
  "warehouse_id": "68ba4460-…", "zone_id": "0dad8bdf-…",
  "supplier_id": "1e972541-…",
  "items": [{
    "product_id": "e20e5121-…", "quantity": 20, "unit_cost": 15500,
    "lot_number": "L-2026-007", "expiry_date": "2027-03-31",
    "bin_id": "6b1f0c0a-…"
  }]
}
// RESPONSE 201
{
  "transaction_id": "3ce60820-…", "transaction_type": "RECEIPT",
  "timestamp": "2026-11-04T19:45:14.420588Z", "status": "COMPLETED", "items_processed": 1,
  "document_number": "E-000002"
}
```

## 2. Salidas, traslados y ajustes

| Endpoint | Entrada nueva (opcional) |
|---|---|
| `POST /v1/transactions/issues` | `items[].bin_id`, `items[].supplier_id` |
| `POST /v1/transactions/transfers` | `items[].from_bin_id` (de `source_zone_id`), `items[].to_bin_id` (de `target_zone_id`), `items[].supplier_id` |
| `POST /v1/transactions/adjustments` | `items[].bin_id`, `items[].supplier_id` (`lot_number` y `reason` siguen igual) |

- En un traslado, el lote **viaja con su proveedor**; solo cambian la zona y/o el bin.
- `supplier_id` en una salida solo hace falta si el mismo `lot_number` existe de **dos
  proveedores** en esa ubicación. Sin él, la API responde `409` pidiéndolo.

```json
// POST /v1/transactions/transfers — mover 3 unidades del estante N1 al N2 de la misma zona
{
  "reference_id": "TRF-2026-00034",
  "source_warehouse_id": "68ba4460-…", "source_zone_id": "0dad8bdf-…",
  "target_warehouse_id": "68ba4460-…", "target_zone_id": "0dad8bdf-…",
  "items": [{ "product_id": "e20e5121-…", "quantity": 3, "lot_number": "L-2026-007",
              "from_bin_id": "6b1f0c0a-…", "to_bin_id": "849c96bb-…" }]
}
```

## 3. Lote obligatorio con `track_lots = true`

Entradas, ajustes y traslados de un producto con `track_lots = true` **sin `lot_number`**
responden `422`:

```json
{ "detail": "El producto FILTRO-001 maneja lotes (track_lots = true): el ítem debe incluir lot_number.", … }
```

Las **reservas no se rechazan**: el inventario elige el lote (sección 4).

## 4. Reservas — `POST /v1/reservations` (+ confirmar y cancelar)

**Entrada nueva (opcional, por ítem):** `lot_number`, `bin_id`, `supplier_id`.

**Cómo elige el lote el inventario** cuando no se envía `lot_number` y el producto tiene `track_lots`:
1. Primero el que **vence antes** (FEFO).
2. Sin vencimientos, el que **entró primero** (FIFO).
3. Si un lote no alcanza, la reserva **se reparte** en varios.

**Respuesta nueva, por ítem:**

| Campo | Descripción |
|---|---|
| `lot_number`, `bin_id`, `supplier_id` | Lo que se pidió (null = lo eligió el inventario). |
| `allocations[]` | **Desglose real**: `{lot_number, bin_id, bin_code, bin_name, supplier_id, expiry_date, quantity, confirmed_qty}` en orden de consumo. |

```json
// REQUEST — Appits no indica lote
{ "reference_type": "WORK_ORDER", "reference_id": "OT-2026-00892",
  "items": [{ "product_id": "e20e5121-…", "warehouse_id": "68ba4460-…", "zone_id": "0dad8bdf-…", "quantity": 25 }] }

// RESPONSE 201 — se repartió en dos lotes, primero el que vence antes
{
  "id": "95add655-…", "reference_type": "WORK_ORDER", "reference_id": "OT-2026-00892", "status": "ACTIVE", …,
  "items": [{
    "id": "fa908363-…", "product_id": "e20e5121-…", "warehouse_id": "68ba4460-…", "zone_id": "0dad8bdf-…",
    "quantity": "25.0000", "confirmed_qty": "0.0000",
    "lot_number": null, "bin_id": null, "supplier_id": null,
    "allocations": [
      { "lot_number": "L-2026-007", "bin_id": "6b1f0c0a-…", "bin_code": "E3-F1-N1", "bin_name": "Estante E3-F1-N1",
        "supplier_id": "1e972541-…", "expiry_date": "2027-03-31", "quantity": "20.0000", "confirmed_qty": "0.0000" },
      { "lot_number": "L-2026-031", "bin_id": "849c96bb-…", "bin_code": "E3-F1-N2", "bin_name": "Estante E3-F1-N2",
        "supplier_id": "5f4b8d33-…", "expiry_date": "2027-12-31", "quantity": "5.0000", "confirmed_qty": "0.0000" }
    ]
  }]
}
```

**Confirmar — `POST /v1/reservations/{id}/confirm`** (el cuerpo no cambia).
La respuesta trae el mismo desglose con `confirmed_qty` = lo que salió de cada lote. Se despacha
en el orden de `allocations`; si se confirma menos de lo reservado, se libera lo que sobra.
En el ledger queda **un `ISSUE` por lote/bin**, con `reference_id` = el `reference_id` de la
reserva (la orden de Appits) y su `transaction_id`.

```json
// REQUEST
{ "actual_quantity_to_issue": 25, "issue_reference": "OT-2026-00892" }
// RESPONSE 200 (extracto)
"allocations": [
  { "lot_number": "L-2026-007", "bin_code": "E3-F1-N1", "quantity": "20.0000", "confirmed_qty": "20.0000", … },
  { "lot_number": "L-2026-031", "bin_code": "E3-F1-N2", "quantity": "5.0000",  "confirmed_qty": "5.0000",  … }
]
```

**Cancelar** y la **expiración automática** liberan exactamente lo que cada asignación apartó.

## 5. Saldos — `GET /v1/stock/balances`

**Filtros nuevos:** `lot_number`, `bin_id`, `supplier_id`.
**Respuesta nueva, por saldo:** `bin_id`, `bin_code`, `bin_name`, `supplier_id`, `expiry_date` (vencimiento del lote).

```json
// GET /v1/stock/balances?lot_number=L-2026-007   → "¿dónde está el lote y de qué proveedor vino?"
{ "data": [{
    "id": "e9fa7d8c-…", "product_id": "e20e5121-…", "warehouse_id": "68ba4460-…", "zone_id": "0dad8bdf-…",
    "lot_number": "L-2026-007", "physical_qty": "20.0000", "reserved_qty": "0.0000", "available_qty": "20.0000",
    "bin_id": "6b1f0c0a-…", "bin_code": "E3-F1-N1", "bin_name": "Estante E3-F1-N1",
    "supplier_id": "1e972541-…", "expiry_date": "2027-03-31"
  }], "pagination": { … } }
```

`GET /v1/stock/balances?bin_id=…` responde "¿qué hay en el estante 3?".

## 6. Ledger — `GET /v1/ledger`

**Filtros nuevos:** `lot_number`, `zone_id`, `bin_id`, `supplier_id`, `reference_id`,
`document_number`, `date_from`, `date_to` (YYYY-MM-DD, ambos inclusivos, UTC).

**Respuesta nueva, por movimiento:** `bin_id`, `bin_code`, `bin_name`, `supplier_id`,
`expiry_date`, `document_number`.

```json
// GET /v1/ledger?lot_number=L-2026-007   → entrada del proveedor + órdenes en que se usó
{ "data": [
  { "movement_type": "ISSUE", "qty_change": "-20.0000", "lot_number": "L-2026-007",
    "reference_type": "RESERVATION_CONFIRM", "reference_id": "OT-2026-00892",
    "transaction_id": "66485755-…", "bin_code": "E3-F1-N1", "supplier_id": "1e972541-…", "document_number": null, … },
  { "movement_type": "RECEIPT", "qty_change": "20.0000", "lot_number": "L-2026-007",
    "reference_type": "PURCHASE_ORDER", "reference_id": "OC-2026-00146",
    "bin_code": "E3-F1-N1", "supplier_id": "1e972541-…", "expiry_date": "2027-03-31", "document_number": "E-000002", … }
], "pagination": { … } }
```

## 7. Lotes — `POST /v1/batches` / `GET /v1/batches`

**Entrada y respuesta nuevas:** `supplier_id` (opcional). El número es único por
producto + proveedor: `409` solo si el **mismo** proveedor repite el número.

---

## Cambios de comportamiento que Appits debe conocer

1. **`track_lots = true` exige lote** en entradas, ajustes y traslados (`422`). Si Appits hoy
   hace entradas sin lote de productos con `track_lots = true`, esas llamadas empezarán a fallar.
2. **Confirmar más de lo reservado** responde `422`. Antes se aceptaba y descontaba de más.
3. **`reference_id` del ISSUE de una confirmación** es ahora el de la reserva (la orden). Antes
   era el `issue_reference` de la confirmación. Si Appits manda el mismo valor en ambos, no cambia nada.

Y una corrección: `GET /v1/ledger` respondía `500` en cuanto existía una reserva confirmada.
Esas filas antiguas ahora salen con `transaction_id: null`; las nuevas siempre lo traen.

## Aislamiento entre tenants

Un `bin_id` o `supplier_id` de otro tenant responde `404`, igual que si no existiera. Un lote
de otro tenant no aparece en saldos ni en el ledger, y reservarlo responde `409` (sin stock).
