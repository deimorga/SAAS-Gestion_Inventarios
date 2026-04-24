# Definición Técnica — Módulo 06: Reportes y Valoración

**Versión:** 1.0  
**Estado:** Borrador  
**Fecha:** 2026-04-24  
**RF Cubiertos:** RF-026 a RF-029  
**Prioridad:** P2  
**Autor:** Agente Antigravity (Arquitecto de Soluciones)

---

> [!IMPORTANT]
> Los endpoints de este módulo pueden realizar consultas intensivas a la base de datos (Kardex, Valoración). Se deben usar paginación estricta y, en escenarios de alto volumen, encolar el reporte para descarga asíncrona.

## 1. Resumen de Endpoints

| # | Método | Endpoint | RF | Descripción | Scope |
|---|--------|----------|----|-------------|-------|
| 1 | `GET` | `/v1/reports/kardex` | RF-026 | Histórico de movimientos por producto (Kardex) | `READ_INVENTORY` |
| 2 | `GET` | `/v1/reports/valuation` | RF-027 | Valoración de inventario (CPP actual) | `READ_INVENTORY` |
| 3 | `POST` | `/v1/reports/valuation/snapshots` | RF-027 | Guardar snapshot contable (Cierre de mes) | `ADMIN` |
| 4 | `GET` | `/v1/reports/low-stock` | RF-028 | Alertas de reabastecimiento | `READ_INVENTORY` |

---

## 2. Contratos API Detallados

### 2.1 GET `/v1/reports/kardex` — Histórico de Movimientos (Kardex)

**RF:** RF-026 | **Tablas:** `inventory_ledger`, `products`, `warehouses`

#### Query Parameters

| Param | Tipo | Requerido | Descripción |
|-------|------|:---------:|-------------|
| `product_id` | `uuid` | ✅ | Producto a consultar |
| `warehouse_id`| `uuid` | ❌ | Filtrar por almacén |
| `date_from` | `datetime` | ❌ | Fecha de inicio |
| `date_to` | `datetime` | ❌ | Fecha de fin |
| `page` | `int` | ❌ | Default: 1 |
| `page_size` | `int` | ❌ | Default: 50 |

#### Response — `200 OK`

```json
{
  "product": {
    "id": "prod-uuid",
    "sku": "MON-24",
    "current_cpp": 420000.00
  },
  "initial_balance": 10.0,
  "final_balance": 55.0,
  "movements": [
    {
      "id": "ledger-uuid-1",
      "date": "2026-04-24T10:00:00Z",
      "type": "RECEIPT",
      "reason": "COMPRA_PROVEEDOR",
      "reference": "PO-123",
      "qty_in": 50.0,
      "qty_out": 0.0,
      "unit_cost": 425000.00,
      "balance_after": 60.0
    },
    {
      "id": "ledger-uuid-2",
      "date": "2026-04-24T14:00:00Z",
      "type": "ISSUE",
      "reason": "VENTA",
      "reference": "SO-456",
      "qty_in": 0.0,
      "qty_out": 5.0,
      "unit_cost": 425000.00, 
      "balance_after": 55.0
    }
  ],
  "pagination": { "page": 1, "page_size": 50, "total": 2 }
}
```

> [!NOTE]
> El `balance_after` se calcula dinámicamente o se puede almacenar de forma desnormalizada en el `inventory_ledger` en el momento de la inserción para facilitar la lectura del Kardex.

---

### 2.2 GET `/v1/reports/valuation` — Valoración de Inventario

**RF:** RF-027 | **Tablas:** `products`, `stock_balances`

#### Query Parameters

| Param | Tipo | Descripción |
|-------|------|-------------|
| `category_id` | `uuid` | Agrupar/filtrar por categoría |
| `warehouse_id`| `uuid` | Filtrar por almacén |

#### Response — `200 OK`

```json
{
  "total_valuation": 150000000.00,
  "currency": "COP",
  "details": [
    {
      "product_id": "prod-uuid-1",
      "sku": "MON-24",
      "name": "Monitor 24",
      "total_qty": 50.0,
      "current_cpp": 420000.00,
      "total_value": 21000000.00
    }
  ]
}
```

---

### 2.3 POST `/v1/reports/valuation/snapshots` — Snapshot Contable

**RF:** RF-027 | **Tablas:** `valuation_snapshots`

Para cumplir con el cierre contable de fin de mes, este endpoint captura el saldo y costo exacto en el momento de invocarse y lo congela en una tabla histórica.

#### Request

```json
{
  "period": "2026-04",
  "description": "Cierre Contable Abril 2026"
}
```

#### Response — `202 Accepted`

```json
{
  "message": "Snapshot en proceso. Se notificará al finalizar.",
  "snapshot_id": "snap-uuid-1"
}
```

> [!WARNING]
> La generación del snapshot puede ser pesada. La API debe delegar el trabajo a un Background Task (Celery) que itere sobre `stock_balances` e inserte copias estáticas en `valuation_snapshots`.

---

### 2.4 GET `/v1/reports/low-stock` — Alertas de Reabastecimiento

**RF:** RF-028 | **Tablas:** `products`, `stock_balances`

Retorna productos donde `available_qty <= reorder_point`.

#### Response — `200 OK`

```json
{
  "data": [
    {
      "product_id": "prod-uuid-mouse",
      "sku": "MOU-001",
      "name": "Mouse Inalámbrico",
      "available_qty": 2.0,
      "reorder_point": 10.0,
      "deficit": 8.0,
      "suggested_suppliers": [
        { "id": "supp-uuid-1", "name": "TechCo", "last_cost": 45000.0 }
      ]
    }
  ]
}
```

---

## 3. Tablas de Base de Datos Afectadas

| Tabla | Operación | RLS | Descripción |
|-------|-----------|:---:|-------------|
| `valuation_snapshots` | INSERT (Celery), READ | ✅ | Tabla nueva para fotos contables de fin de mes |

### Modelo Sugerido para Snapshots

```sql
CREATE TABLE valuation_snapshots (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    period VARCHAR(20) NOT NULL,
    product_id UUID NOT NULL,
    snapshot_qty DECIMAL NOT NULL,
    snapshot_cpp DECIMAL NOT NULL,
    total_value DECIMAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_snapshots_tenant_period ON valuation_snapshots(tenant_id, period);
```

---

## 4. Modelo Pydantic (Schemas Python)

```python
class SnapshotCreate(BaseModel):
    period: str = Field(..., description="Formato YYYY-MM")
    description: str | None = None

class KardexFilter(BaseModel):
    product_id: UUID
    warehouse_id: UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
```
