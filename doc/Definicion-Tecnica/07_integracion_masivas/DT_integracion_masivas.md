# Definición Técnica — Módulo 07: Integraciones y Masivos

**Versión:** 1.0  
**Estado:** Borrador  
**Fecha:** 2026-04-24  
**RF Cubiertos:** RF-030 a RF-035  
**Prioridad:** P2  
**Autor:** Agente Antigravity (Arquitecto de Soluciones)

---

> [!IMPORTANT]
> Las integraciones y procesos masivos deben desacoplarse del hilo principal HTTP. Todo endpoint de importación masiva o webhook de salida debe usar el stack de Celery + Redis.

## 1. Resumen de Endpoints

| # | Método | Endpoint | RF | Descripción | Scope |
|---|--------|----------|----|-------------|-------|
| 1 | `POST` | `/v1/imports/products` | RF-030 | Carga masiva de catálogo (CSV/Excel) | `WRITE_CATALOG` |
| 2 | `GET` | `/v1/jobs/{job_id}` | RF-030 | Estado de procesamiento asíncrono | `ADMIN` |
| 3 | `POST` | `/v1/webhooks/endpoints` | RF-032 | Configurar URL destino para webhooks | `ADMIN` |
| 4 | `GET` | `/v1/webhooks/endpoints` | RF-032 | Listar webhooks configurados | `ADMIN` |

---

## 2. Contratos API Detallados

### 2.1 POST `/v1/imports/products` — Importación Masiva

**RF:** RF-030 | **Tablas:** `background_jobs`

La carga de un archivo CSV de 10,000 líneas no puede bloquear la API.

#### Request (multipart/form-data)

- `file`: Archivo CSV
- `update_existing`: `true/false` (Si el SKU ya existe, ¿actualiza o ignora?)

#### Response — `202 Accepted`

```json
{
  "message": "Archivo recibido. El procesamiento ha iniciado en segundo plano.",
  "job_id": "job-uuid-12345",
  "status_url": "/v1/jobs/job-uuid-12345"
}
```

#### Lógica de Negocio (Celery)

1. Guardar archivo en disco temporal o MinIO (`S3`).
2. Crear registro en `background_jobs` con estado `PENDING`.
3. Encolar tarea en Celery: `import_products_task.delay(job_id, file_path, tenant_id)`.
4. El Worker procesa el CSV línea por línea:
   - Validar schema.
   - Insertar/Actualizar en `products`.
   - Llevar contador de éxitos y errores (guardar log de errores).
5. Actualizar `background_jobs` a `COMPLETED` o `FAILED`.

---

### 2.2 GET `/v1/jobs/{job_id}` — Estado de Tarea Asíncrona

**RF:** RF-030 | **Tablas:** `background_jobs`

#### Response — `200 OK`

```json
{
  "job_id": "job-uuid-12345",
  "type": "IMPORT_PRODUCTS",
  "status": "COMPLETED",
  "progress_percentage": 100,
  "result": {
    "total_rows": 500,
    "success_count": 498,
    "error_count": 2,
    "errors": [
      { "row": 45, "error": "Categoría no existe" },
      { "row": 112, "error": "SKU inválido" }
    ]
  },
  "created_at": "2026-04-24T10:00:00Z",
  "completed_at": "2026-04-24T10:02:15Z"
}
```

---

### 2.3 POST `/v1/webhooks/endpoints` — Configurar Webhooks

**RF:** RF-032 | **Tablas:** `webhook_endpoints`

#### Request

```json
{
  "url": "https://mi-ecommerce.com/api/webhooks/micronuba",
  "events": ["stock.changed", "reservation.expired"],
  "secret": "my-shared-secret-123"
}
```

#### Response — `201 Created`

```json
{
  "id": "wh-uuid",
  "url": "https://mi-ecommerce.com/api/webhooks/micronuba",
  "events": ["stock.changed", "reservation.expired"],
  "is_active": true
}
```

---

### 2.4 Payload Estándar de Webhooks de Salida (RF-032)

Cuando un evento ocurre en MicroNuba (ej. salida de inventario), el Worker de Celery dispara un POST a la URL configurada por el cliente.

#### Request desde Celery hacia URL del Cliente:

**Headers:**
```
x-micronuba-signature: sha256=abcdef123456... (HMAC usando secret)
Content-Type: application/json
```

**Body (`stock.changed`):**
```json
{
  "event_id": "evt-uuid-1",
  "event_type": "stock.changed",
  "timestamp": "2026-04-24T15:00:00Z",
  "tenant_id": "tenant-uuid",
  "data": {
    "product_id": "prod-uuid-1",
    "sku": "MON-24",
    "warehouse_id": "wh-uuid-1",
    "old_available_qty": 50.0,
    "new_available_qty": 45.0,
    "reason": "ISSUE_CONFIRMED"
  }
}
```

#### Lógica de Resiliencia del Webhook (Celery)
- Si el destino responde `5xx` o hay timeout, Celery debe aplicar política de reintentos exponencial (ej. 3 reintentos: 1m, 5m, 15m).
- Si falla permanentemente, registrar en log de errores del tenant.

---

## 3. Tablas de Base de Datos Afectadas

| Tabla | Uso | RLS |
|-------|-----|:---:|
| `background_jobs` | Controlar estado de tareas masivas | ✅ |
| `webhook_endpoints` | Destinos configurados por tenant | ✅ |

### SQL DDL (Propuesta)

```sql
CREATE TABLE background_jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- PENDING, PROCESSING, COMPLETED, FAILED
    progress_percentage INTEGER DEFAULT 0,
    result_payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE webhook_endpoints (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(255),
    events JSONB NOT NULL, -- ["stock.changed", ...]
    is_active BOOLEAN DEFAULT TRUE
);
```

---

## 4. Modelo Pydantic (Schemas Python)

```python
class WebhookEndpointCreate(BaseModel):
    url: HttpUrl
    events: list[str] = Field(..., min_length=1)
    secret: str = Field(..., min_length=16, max_length=100)

class JobStatusResponse(BaseModel):
    job_id: UUID
    type: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    progress_percentage: int
    result: dict | None
    created_at: datetime
    completed_at: datetime | None
```

---

## 5. Bulk Engine — Endpoints Reales (Implementado)

> Los endpoints de importación CSV no están activos en el MVP. La carga masiva se hace vía JSON síncrono con `/v1/bulk/*`.

### 5.1 POST `/v1/bulk/receipts` — Entradas masivas

Procesa hasta **500 entradas de mercancía** en un solo request. Cada ítem es atómico e independiente — un fallo parcial no bloquea el lote.

#### Request

```json
{
  "items": [
    {
      "reference_type": "PURCHASE_ORDER",
      "reference_id": "OC-2026-00145",
      "reason_code": "COMPRA",
      "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
      "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
      "items": [
        {
          "product_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "quantity": 10,
          "unit_cost": 15500.00
        }
      ]
    },
    {
      "reference_type": "PURCHASE_ORDER",
      "reference_id": "OC-2026-00146",
      "reason_code": "COMPRA",
      "warehouse_id": "b1c2d3e4-f5a6-7890-bcde-f01234567891",
      "zone_id": "c2d3e4f5-a6b7-8901-cdef-012345678902",
      "items": [
        {
          "product_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "quantity": 5,
          "unit_cost": 8900.00
        }
      ]
    }
  ]
}
```

#### Response — `200 OK`

```json
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "status": "ok",
      "transaction_id": "txn-uuid-001",
      "detail": null
    },
    {
      "index": 1,
      "status": "ok",
      "transaction_id": "txn-uuid-002",
      "detail": null
    }
  ]
}
```

#### Response con fallo parcial

```json
{
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "results": [
    { "index": 0, "status": "ok", "transaction_id": "txn-uuid-001", "detail": null },
    { "index": 1, "status": "error", "transaction_id": null, "detail": "Producto a1b2... no encontrado o inactivo" }
  ]
}
```

Los endpoints equivalentes son:
- `POST /v1/bulk/issues` — salidas masivas (misma estructura, items son IssueRequest)
- `POST /v1/bulk/transfers` — transferencias masivas (items son TransferRequest)

---

## 6. Webhooks — Corrección de Implementación

### 6.1 Eventos válidos

| Evento | Cuándo se dispara |
|--------|-------------------|
| `transaction.receipt` | Se registra una entrada de mercancía |
| `transaction.issue` | Se registra una salida de mercancía |
| `transaction.transfer` | Se registra una transferencia entre almacenes |
| `transaction.adjustment` | Se registra un ajuste de inventario |
| `reservation.created` | Se crea una reserva |
| `reservation.confirmed` | Se confirma (convierte en Issue) una reserva |
| `reservation.cancelled` | Se cancela una reserva |
| `reservation.expired` | Celery expira una reserva por TTL |
| `stock.low` | El available_qty cae por debajo del reorder_point |

### 6.2 Firma HMAC — Paso a paso

El servidor envía `X-Webhook-Signature: sha256=<hex>` y `X-Webhook-Event: <event_type>`.

**Algoritmo de verificación en el receptor:**

```python
import hmac, hashlib

def verify_signature(payload_bytes: bytes, secret: str, header: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)

# En tu endpoint Flask/FastAPI:
raw_body = await request.body()
sig_header = request.headers.get("X-Webhook-Signature", "")
if not verify_signature(raw_body, MY_WEBHOOK_SECRET, sig_header):
    return Response(status_code=401)
```

**Verificación equivalente en Node.js:**

```javascript
const crypto = require('crypto');
const sig = 'sha256=' + crypto
  .createHmac('sha256', MY_WEBHOOK_SECRET)
  .update(rawBody)
  .digest('hex');
const isValid = crypto.timingSafeEqual(
  Buffer.from(sig), Buffer.from(incomingSignature)
);
```

### 6.3 Payload estándar por evento (corregido)

**`transaction.receipt` / `transaction.issue`:**

```json
{
  "event_id": "evt-uuid-001",
  "event_type": "transaction.receipt",
  "timestamp": "2026-05-14T15:00:00Z",
  "tenant_id": "tenant-uuid",
  "data": {
    "transaction_id": "txn-uuid-001",
    "reference_type": "PURCHASE_ORDER",
    "reference_id": "OC-2026-00145",
    "warehouse_id": "wh-uuid-1",
    "items_processed": 1
  }
}
```

**`stock.low`:**

```json
{
  "event_id": "evt-uuid-002",
  "event_type": "stock.low",
  "timestamp": "2026-05-14T15:05:00Z",
  "tenant_id": "tenant-uuid",
  "data": {
    "product_id": "prod-uuid-1",
    "sku": "FILTRO-ACEITE-001",
    "warehouse_id": "wh-uuid-1",
    "available_qty": 2.0,
    "reorder_point": 5.0
  }
}
```

**`reservation.expired`:**

```json
{
  "event_id": "evt-uuid-003",
  "event_type": "reservation.expired",
  "timestamp": "2026-05-14T16:00:00Z",
  "tenant_id": "tenant-uuid",
  "data": {
    "reservation_id": "res-uuid-1",
    "reference_type": "ECOMMERCE_CART",
    "reference_id": "CART-12345"
  }
}
```
