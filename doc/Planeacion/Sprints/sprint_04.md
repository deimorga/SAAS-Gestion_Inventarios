# Sprint 4 — Webhooks, Bulk Engine e Inventario Cíclico

**Fecha Inicio:** 2026-04-28
**Fecha Fin Real:** 2026-04-28
**Estado:** ✅ Completado

---

## 🎯 Objetivo del Sprint

Conectar MicroNuba con el ecosistema externo y habilitar operaciones de alta escala. El sprint cubre tres módulos: (1) **Webhooks** para push de eventos en tiempo real hacia sistemas externos (ERP, e-commerce, WMS), (2) **Bulk Engine** para importación masiva de movimientos sin saturar la API uno-a-uno, y (3) **Inventario Cíclico** para verificar físicamente el stock y reconciliar diferencias mediante ajustes automáticos.

---

## 📋 Items del Sprint

| ID | Requerimiento | Tarea | Estado | Notas |
|---|---|---|---|---|
| T-401 | RF-033 | Webhook Endpoints Registry — CRUD de URLs de destino | ✅ Completado | Tablas `webhook_endpoints` + `webhook_deliveries`; migración 006 |
| T-402 | RF-033 | Webhook Dispatcher — envío HTTP + reintento exponencial | ✅ Completado | Background loop; HMAC-SHA256 signing; `X-Webhook-Signature` |
| T-403 | RF-034 | Bulk Engine — Receipts + Issues masivos (hasta 500 items) | ✅ Completado | Validación por ítem; respuesta parcial success/failure |
| T-404 | RF-034 | Bulk Engine — Transfers masivos + report de resultado | ✅ Completado | Depende de T-403; mismo patrón pero con zona origen/destino |
| T-405 | RF-035 | Inventario Cíclico — Sesiones y captura de expected_qty | ✅ Completado | Tablas `cycle_count_sessions` + `cycle_count_items`; migración 007 |
| T-406 | RF-035 | Inventario Cíclico — Conteo, cierre y ajustes automáticos | ✅ Completado | `POST /{id}/close`; genera `ADJUSTMENT` si `apply_adjustments=true` |

---

## 🗄️ Modelo de Datos Nuevo

### Migración 006 — Webhooks

#### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `webhook_endpoints` | URLs de destino registradas por cada tenant con sus eventos suscritos | ✅ |
| `webhook_deliveries` | Historial de envíos: payload, estado, intentos y código de respuesta | ✅ |

#### DDL referencia

```sql
-- webhook_endpoints
CREATE TABLE webhook_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret VARCHAR(128) NOT NULL,          -- usado para firma HMAC-SHA256
    events JSONB NOT NULL DEFAULT '[]',    -- ej. ["transaction.receipt","reservation.expired"]
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_webhook_endpoints_tenant ON webhook_endpoints(tenant_id, is_active);
ALTER TABLE webhook_endpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_endpoints FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON webhook_endpoints
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- webhook_deliveries
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    endpoint_id UUID NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',   -- PENDING / DELIVERED / FAILED
    attempts INTEGER NOT NULL DEFAULT 0,
    last_response_code INTEGER,
    last_response_body TEXT,
    next_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_webhook_deliveries_dispatch ON webhook_deliveries(status, next_attempt_at);
CREATE INDEX idx_webhook_deliveries_tenant ON webhook_deliveries(tenant_id, created_at DESC);
ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_deliveries FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON webhook_deliveries
    USING (tenant_id::text = current_setting('app.current_tenant', true));
```

### Migración 007 — Inventario Cíclico

#### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `cycle_count_sessions` | Sesión de conteo cíclico para un almacén (`OPEN` / `CLOSED`) | ✅ |
| `cycle_count_items` | Líneas de conteo: expected_qty (foto inicial) y counted_qty (recuento real) | ✅ |

#### DDL referencia

```sql
-- cycle_count_sessions
CREATE TABLE cycle_count_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    label VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',   -- OPEN / CLOSED
    apply_adjustments BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ
);
CREATE INDEX idx_cycle_sessions_tenant ON cycle_count_sessions(tenant_id, status);
ALTER TABLE cycle_count_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_count_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON cycle_count_sessions
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- cycle_count_items
CREATE TABLE cycle_count_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES cycle_count_sessions(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    zone_id UUID NOT NULL REFERENCES zones(id),
    expected_qty DECIMAL(18,4) NOT NULL,
    counted_qty DECIMAL(18,4),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_cycle_items_session ON cycle_count_items(session_id);
ALTER TABLE cycle_count_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_count_items FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON cycle_count_items
    USING (tenant_id::text = current_setting('app.current_tenant', true));
```

> **Nota:** La varianza se calcula en servicio (`counted_qty - expected_qty`) en lugar de columna generada, para compatibilidad con la versión de PostgreSQL del proyecto.

---

## 🌐 Endpoints Nuevos

### Webhooks — `/v1/webhooks`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/webhooks` | RF-033 | Registrar nuevo endpoint de destino |
| `GET` | `/v1/webhooks` | RF-033 | Listar endpoints del tenant |
| `GET` | `/v1/webhooks/{id}` | RF-033 | Detalle de endpoint |
| `PATCH` | `/v1/webhooks/{id}` | RF-033 | Actualizar URL / eventos / estado activo |
| `DELETE` | `/v1/webhooks/{id}` | RF-033 | Eliminar endpoint |
| `POST` | `/v1/webhooks/{id}/test` | RF-033 | Enviar ping de prueba (`{"event":"ping","timestamp":"..."}`) |
| `GET` | `/v1/webhooks/{id}/deliveries` | RF-033 | Historial de entregas del endpoint |

#### Catálogo de eventos soportados

| Evento | Disparado cuando |
|---|---|
| `transaction.receipt` | Nueva entrada de mercancía registrada |
| `transaction.issue` | Nueva salida de mercancía registrada |
| `transaction.transfer` | Nueva transferencia inter-almacén |
| `transaction.adjustment` | Ajuste de auditoría registrado |
| `reservation.created` | Reserva nueva creada |
| `reservation.confirmed` | Reserva confirmada (convertida a Issue) |
| `reservation.cancelled` | Reserva cancelada manualmente |
| `reservation.expired` | Reserva expirada por background worker |
| `stock.low` | Stock disponible ≤ reorder_point (emitido al cerrar una transacción) |

#### Firma de seguridad

Cada envío incluye el header `X-Webhook-Signature: sha256=<hmac>` usando el `secret` del endpoint. El receptor puede verificar la autenticidad del payload.

```
HMAC-SHA256(secret, body_bytes) → hex → "sha256=<hex>"
```

### Bulk Engine — `/v1/bulk`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/bulk/receipts` | RF-034 | Lote de entradas de mercancía (máx. 500 ítems) |
| `POST` | `/v1/bulk/issues` | RF-034 | Lote de salidas (máx. 500 ítems) |
| `POST` | `/v1/bulk/transfers` | RF-034 | Lote de transferencias (máx. 500 ítems) |

#### Formato de respuesta (parcial success)

```json
{
    "total": 100,
    "succeeded": 95,
    "failed": 5,
    "results": [
        {"index": 0, "status": "ok", "transaction_id": "uuid"},
        {"index": 3, "status": "error", "detail": "Stock insuficiente para producto X en zona Y"}
    ]
}
```

Cada ítem se procesa de forma independiente; un error en uno no detiene el lote. El HTTP status es `200` si al menos uno tuvo éxito, `422` si todos fallaron.

### Inventario Cíclico — `/v1/cycle-counts`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/cycle-counts` | RF-035 | Iniciar sesión para un almacén; captura `expected_qty` de `stock_balances` |
| `GET` | `/v1/cycle-counts` | RF-035 | Listar sesiones del tenant (`status` opcional) |
| `GET` | `/v1/cycle-counts/{id}` | RF-035 | Detalle de sesión con items y varianzas calculadas |
| `PATCH` | `/v1/cycle-counts/{id}/items/{item_id}` | RF-035 | Registrar `counted_qty` para un ítem |
| `POST` | `/v1/cycle-counts/{id}/close` | RF-035 | Cerrar sesión; si `apply_adjustments=true` → genera `ADJUSTMENT` por varianza ≠ 0 |

---

## 🔑 Dependencias y Patrones de Implementación

### Patrones heredados (mantener)

- `UUID(as_uuid=False)` en todos los modelos SQLAlchemy nuevos.
- RLS en todas las tablas nuevas: `ENABLE + FORCE + CREATE POLICY tenant_isolation`.
- `str(r.id)`, `str(r.product_id)`, etc. en servicios al leer UUID de queries `text()`.
- Convención DOC-001: `summary` + `description` + `responses` + examples en cada endpoint nuevo.
- Auth codes: 401 para no autenticado, 403 para rol incorrecto.

### Nuevos patrones a introducir

- **Webhook dispatcher loop:** segundo `asyncio.create_task` en lifespan; itera `webhook_deliveries` con `status=PENDING` y `next_attempt_at <= now()`. Debe iterar por tenant (RLS FORCE). Reintento con backoff: 30s → 5min → 30min (máx 3 intentos).
- **HMAC signing:** `hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()` — no depende de librerías externas.
- **Bulk partial success:** cada ítem en try/except independiente dentro del endpoint; acumular resultados; rollback individual por ítem (savepoint o sesión por ítem).
- **Cycle count snapshot:** al crear sesión, `INSERT INTO cycle_count_items SELECT ...` desde `stock_balances` del almacén. Operación atómica con la cabecera.

---

## 📂 Estructura de Archivos Nuevos

```
core_backend/
├── alembic/versions/
│   ├── 006_webhooks.py                        # tablas webhook_endpoints, webhook_deliveries
│   └── 007_cycle_counts.py                    # tablas cycle_count_sessions, cycle_count_items
├── app/
│   ├── models/
│   │   ├── webhook.py                         # WebhookEndpoint, WebhookDelivery
│   │   └── cycle_count.py                     # CycleCountSession, CycleCountItem
│   ├── schemas/
│   │   ├── webhook.py                         # Create/Response/Delivery schemas
│   │   ├── bulk.py                            # BulkReceipt/Issue/Transfer/Result schemas
│   │   └── cycle_count.py                     # Session/Item/Close schemas
│   ├── services/
│   │   ├── webhook.py                         # CRUD + dispatcher + signing
│   │   ├── bulk.py                            # process_bulk_receipts/issues/transfers
│   │   └── cycle_count.py                     # create/list/get/record/close session
│   └── api/v1/endpoints/
│       ├── webhooks.py                        # 7 endpoints
│       ├── bulk.py                            # 3 endpoints
│       └── cycle_counts.py                    # 5 endpoints
└── tests/
    ├── test_webhooks.py                       # ~15 tests
    ├── test_bulk.py                           # ~12 tests
    └── test_cycle_counts.py                   # ~12 tests
```

---

## 🚦 Criterios de Aceptación (DoD)

| Criterio | Umbral | Estado |
|----------|--------|--------|
| Cobertura global ≥80% | ≥80% | ✅ 91% |
| 0 errores `ruff` | `All checks passed!` | ✅ |
| 0 errores `mypy` | `Success: no issues found` | ✅ 75 archivos |
| RLS validado en tablas nuevas | `webhook_endpoints`, `webhook_deliveries`, `cycle_count_sessions`, `cycle_count_items` | ✅ |
| Webhook firma HMAC verificable | Header `X-Webhook-Signature` presente y correcto en cada envío | ✅ |
| Webhook reintento exponencial | 3 intentos: 30s → 5min → 30min; status → `FAILED` al agotarse | ✅ |
| Bulk respuesta parcial | Fallos individuales no detienen el lote; `results` contiene índice + detalle | ✅ |
| Cycle count cierra con ajustes | `apply_adjustments=true` genera entradas `ADJUSTMENT` en `transactions` + `inventory_ledger` | ✅ |
| Convención DOC-001 aplicada | Todos los endpoints nuevos con `summary` + `description` + `responses` + examples | ✅ |

---

## 📊 Métricas Acumuladas

| Métrica | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 (meta) |
|---------|----------|----------|----------|-----------------|
| Tests totales | 48 | 84 | 111 | **154** |
| Cobertura | 90% | 93% | 92% | **91%** |
| Ruff errors | 0 | 0 | 0 | **0** |
| Mypy errors | 0 | 0 | 0 | **0** |
| Endpoints totales | ~17 | ~27 | ~37 | **~52** |
| Migraciones | 002 | 003 | 004 + 005 | **006 + 007** |
