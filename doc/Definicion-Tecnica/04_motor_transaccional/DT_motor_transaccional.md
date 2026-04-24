# Definición Técnica — Módulo 04: Motor Transaccional

**Versión:** 1.0  
**Estado:** Borrador  
**Fecha:** 2026-04-24  
**RF Cubiertos:** RF-016 a RF-021  
**Prioridad:** P0 — Crítico  
**Autor:** Agente Antigravity (Arquitecto de Soluciones)

---

> [!CAUTION]
> **REGLA DE ORO DEL MOTOR:** 
> 1. El `inventory_ledger` es de **solo anexar** (Append-Only). No hay `UPDATE` ni `DELETE`.
> 2. Las transacciones deben usar bloqueo optimista (Optimistic Concurrency Control) en `stock_balances`.
> 3. Las transacciones compuestas (Transferencias) requieren **transacciones SQL atómicas** (Commit/Rollback).

## 1. Resumen de Endpoints

| # | Método | Endpoint | RF | Descripción | Scope |
|---|--------|----------|----|-------------|-------|
| 1 | `POST` | `/v1/transactions/receipts` | RF-016 | Entrada de inventario (Compras/Devoluciones) | `WRITE_INVENTORY` |
| 2 | `POST` | `/v1/transactions/issues` | RF-017 | Salida de inventario (Ventas/Mermas) | `WRITE_INVENTORY` |
| 3 | `POST` | `/v1/transactions/transfers` | RF-018 | Transferencia entre almacenes/zonas | `WRITE_INVENTORY` |
| 4 | `POST` | `/v1/transactions/adjustments` | RF-019 | Ajustes de inventario (Conteo físico) | `WRITE_INVENTORY` |
| 5 | `GET` | `/v1/stock/balances` | RF-020 | Consulta de saldos consolidados | `READ_INVENTORY` |
| 6 | `GET` | `/v1/ledger` | RF-021 | Historial inmutable de movimientos | `READ_INVENTORY` |

---

## 2. Contratos API Detallados

### 2.1 POST `/v1/transactions/receipts` — Entrada de Inventario

**RF:** RF-016 | **Tablas:** `inventory_ledger`, `stock_balances`, `products` (actualiza CPP)

#### Request

```json
{
  "reference_type": "PURCHASE_ORDER",
  "reference_id": "PO-2026-001",
  "reason_code": "COMPRA_PROVEEDOR",
  "warehouse_id": "wh-uuid-1",
  "zone_id": "zone-uuid-receiving",
  "items": [
    {
      "product_id": "prod-uuid-monitor",
      "quantity": 50.0,
      "unit_cost": 420000.00,
      "lot_number": "LOTE-202604",
      "expiry_date": "2028-12-31"
    }
  ]
}
```

| Campo | Tipo | Requerido | Validación |
|-------|------|:---------:|------------|
| `reference_type` | `string` | ✅ | `PURCHASE_ORDER`, `RETURN_IN`, `INITIAL_STOCK` |
| `reference_id` | `string` | ✅ | ID del documento origen |
| `warehouse_id` | `uuid` | ✅ | Debe estar activo |
| `zone_id` | `uuid` | ✅ | Debe pertenecer al `warehouse_id` |
| `items.quantity` | `decimal` | ✅ | > 0 |
| `items.unit_cost` | `decimal` | ✅ | > 0 (Requerido para cálculo CPP) |

#### Response — `201 Created`

```json
{
  "transaction_id": "tx-uuid-1",
  "transaction_type": "RECEIPT",
  "timestamp": "2026-04-24T10:00:00Z",
  "status": "COMPLETED",
  "items_processed": 1
}
```

#### Lógica de Negocio (ACID)

Por cada ítem en la transacción:
1. **Validar:** Producto activo, zona activa. Si producto exige lote, `lot_number` debe venir.
2. **Ledger:** Insertar en `inventory_ledger` con `qty_change = +50`.
3. **Stock:** 
   - Buscar registro en `stock_balances`. Si no existe, crear con `version=1`.
   - Si existe: `physical_qty += 50`, `available_qty += 50`, `version += 1`.
4. **Valoración (CPP):** 
   - Nuevo CPP = `((StockAntiguo * CPP_Antiguo) + (NuevaCantidad * unit_cost)) / (StockAntiguo + NuevaCantidad)`
   - Actualizar `products.current_cpp`.

---

### 2.2 POST `/v1/transactions/issues` — Salida de Inventario

**RF:** RF-017 | **Tablas:** `inventory_ledger`, `stock_balances`

#### Request

```json
{
  "reference_type": "SALES_ORDER",
  "reference_id": "SO-2026-999",
  "reason_code": "VENTA_CLIENTE",
  "warehouse_id": "wh-uuid-1",
  "zone_id": "zone-uuid-dispatch",
  "items": [
    {
      "product_id": "prod-uuid-monitor",
      "quantity": 5.0,
      "lot_number": "LOTE-202604"
    }
  ]
}
```

#### Errores Críticos

| Código | Condición |
|--------|-----------|
| `409` | Stock insuficiente (`available_qty` < `quantity`) |
| `409` | Error de concurrencia (`VersionMismatchError`) |

#### Lógica de Negocio (ACID)

1. Verificar que `available_qty >= quantity` (a menos que `tenant.allow_negative_stock` sea true).
2. Insertar en `inventory_ledger` con `qty_change = -5`, `unit_cost = products.current_cpp` (salida a costo promedio).
3. Actualizar `stock_balances`: `physical_qty -= 5`, `available_qty -= 5`, `version += 1`.

---

### 2.3 POST `/v1/transactions/transfers` — Transferencias

**RF:** RF-018 | **Tablas:** `inventory_ledger` (x2), `stock_balances` (x2)

#### Request

```json
{
  "reference_type": "INTERNAL_TRANSFER",
  "reference_id": "TR-001",
  "source_warehouse_id": "wh-uuid-1",
  "source_zone_id": "zone-uuid-dispatch",
  "target_warehouse_id": "wh-uuid-transit",
  "target_zone_id": "zone-uuid-transit",
  "items": [
    {
      "product_id": "prod-uuid-monitor",
      "quantity": 10.0
    }
  ]
}
```

#### Lógica de Negocio (ACID)

Una transferencia es estrictamente: **1 Salida + 1 Entrada** atómicas.
1. Iniciar Transacción SQL.
2. Salida del origen (`qty_change = -10`).
3. Entrada al destino (`qty_change = +10`).
4. Si alguna falla (ej: stock insuficiente en origen), `ROLLBACK` completo.
5. `COMMIT`.

---

### 2.4 GET `/v1/stock/balances` — Consulta de Saldos

**RF:** RF-020 | **Tablas:** `stock_balances`

#### Query Parameters

| Param | Tipo | Descripción |
|-------|------|-------------|
| `product_id` | `uuid` | Filtrar por producto |
| `warehouse_id` | `uuid` | Filtrar por almacén |
| `zone_id` | `uuid` | Filtrar por zona |
| `groupBy` | `string` | Agrupar: `warehouse`, `product`, `lot` |

#### Response — `200 OK`

```json
{
  "data": [
    {
      "product_id": "prod-uuid-monitor",
      "sku": "MON-24",
      "warehouse_id": "wh-uuid-1",
      "physical_qty": 45.0,
      "reserved_qty": 5.0,
      "available_qty": 40.0,
      "valuation_total": 18900000.00
    }
  ]
}
```

---

## 3. Optimistic Concurrency Control (OCC)

Para prevenir el problema de sobre-venta (Double-Spending) en concurrencia alta:

```sql
-- UPDATE en stock_balances SIEMPRE valida la versión
UPDATE stock_balances 
SET physical_qty = physical_qty - 5, 
    available_qty = available_qty - 5, 
    version = version + 1 
WHERE product_id = '...' 
  AND zone_id = '...' 
  AND version = 3; -- Versión leída previamente
```

Si el `UPDATE` retorna `0 rows affected`, significa que otro proceso modificó el stock simultáneamente. El backend debe atrapar este caso, re-leer el balance y reintentar (máximo 3 reintentos) antes de lanzar `409 Conflict`.

---

## 4. Tablas de Base de Datos Afectadas

| Tabla | Operación | Endpoints | RLS |
|-------|-----------|-----------|:---:|
| `inventory_ledger` | INSERT (Solo Append) | Receipts, Issues, Transfers | ✅ |
| `stock_balances` | UPSERT | Receipts, Issues, Transfers | ✅ |
| `products` | UPDATE (`current_cpp`) | Receipts (Entradas valorizadas) | ✅ |

### Índices Requeridos

```sql
-- stock_balances
CREATE UNIQUE INDEX idx_stock_product_zone_lot 
ON stock_balances(tenant_id, product_id, zone_id, COALESCE(lot_number, 'N/A'));

-- inventory_ledger
CREATE INDEX idx_ledger_product_date ON inventory_ledger(tenant_id, product_id, created_at DESC);
CREATE INDEX idx_ledger_transaction ON inventory_ledger(tenant_id, transaction_id);
```

---

## 5. Modelo Pydantic (Schemas Python)

```python
class TransactionItemInput(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal | None = Field(None, ge=0)
    lot_number: str | None = None
    serial_number: str | None = None
    expiry_date: date | None = None

class ReceiptRequest(BaseModel):
    reference_type: str = Field(..., max_length=50)
    reference_id: str = Field(..., max_length=100)
    reason_code: str = Field(..., max_length=50)
    warehouse_id: UUID
    zone_id: UUID
    items: list[TransactionItemInput] = Field(..., min_length=1)

class IssueRequest(BaseModel):
    reference_type: str
    reference_id: str
    reason_code: str
    warehouse_id: UUID
    zone_id: UUID
    items: list[TransactionItemInput] = Field(..., min_length=1)

class TransferRequest(BaseModel):
    reference_type: str = "INTERNAL_TRANSFER"
    reference_id: str
    source_warehouse_id: UUID
    source_zone_id: UUID
    target_warehouse_id: UUID
    target_zone_id: UUID
    items: list[TransactionItemInput] = Field(..., min_length=1)
```
