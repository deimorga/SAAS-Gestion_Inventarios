# Definición Técnica — Módulo 05: Reservas y Demanda

**Versión:** 1.0  
**Estado:** Borrador  
**Fecha:** 2026-04-24  
**RF Cubiertos:** RF-022 a RF-025  
**Prioridad:** P1  
**Autor:** Agente Antigravity (Arquitecto de Soluciones)

---

> [!IMPORTANT]
> Una reserva afecta el `available_qty` pero NO el `physical_qty`. Es un compromiso temporal de entrega que se transforma en salida (Issue) o se expira devolviendo disponibilidad.

## 1. Resumen de Endpoints

| # | Método | Endpoint | RF | Descripción | Scope |
|---|--------|----------|----|-------------|-------|
| 1 | `POST` | `/v1/reservations` | RF-022 | Crear una reserva de stock | `MANAGE_RESERVATIONS` |
| 2 | `GET` | `/v1/reservations` | RF-022 | Listar reservas activas | `READ_INVENTORY` |
| 3 | `POST` | `/v1/reservations/{id}/confirm`| RF-023 | Confirmar reserva (Convierte a Issue) | `MANAGE_RESERVATIONS` |
| 4 | `POST` | `/v1/reservations/{id}/cancel` | RF-022 | Cancelar reserva explícitamente | `MANAGE_RESERVATIONS` |
| 5 | `POST` | `/v1/reservations/allocations` | RF-025 | Asignar stock por canales | `MANAGE_RESERVATIONS` |

---

## 2. Contratos API Detallados

### 2.1 POST `/v1/reservations` — Crear Reserva

**RF:** RF-022 | **Tablas:** `reservations`, `stock_balances`

#### Request

```json
{
  "reference_type": "ECOMMERCE_CART",
  "reference_id": "CART-12345",
  "expires_at": "2026-04-24T10:30:00Z",
  "items": [
    {
      "product_id": "prod-uuid-monitor",
      "warehouse_id": "wh-uuid-1",
      "zone_id": "zone-uuid-dispatch",
      "quantity": 2.0
    }
  ]
}
```

| Campo | Tipo | Requerido | Validación |
|-------|------|:---------:|------------|
| `reference_type` | `string` | ✅ | Ej: `ECOMMERCE_CART`, `SALES_QUOTE` |
| `expires_at` | `datetime` | ❌ | Si no se envía, usa `tenant.config.reservation_ttl_minutes` |

#### Response — `201 Created`

```json
{
  "reservation_id": "res-uuid-1",
  "status": "ACTIVE",
  "expires_at": "2026-04-24T10:30:00Z",
  "items_reserved": 2.0
}
```

#### Errores

| Código | Condición |
|--------|-----------|
| `409` | Stock insuficiente (`available_qty` < 2.0) |

#### Lógica de Negocio (ACID)

1. Validar que la cantidad solicitada ≤ `available_qty`.
2. Actualizar `stock_balances`: `reserved_qty += 2`, `available_qty -= 2` (Validando versión OCC).
3. Insertar registro en `reservations` con estado `ACTIVE`.
4. El sistema encolará una tarea asíncrona (Celery/Beat) para liberar esta reserva cuando alcance `expires_at`.

---

### 2.2 POST `/v1/reservations/{id}/confirm` — Confirmar Reserva

**RF:** RF-023 | **Tablas:** `reservations`, `stock_balances`, `inventory_ledger`

#### Request

```json
{
  "actual_quantity_to_issue": 2.0,
  "issue_reference": "INVOICE-999"
}
```

#### Lógica de Negocio (ACID)

Esta operación convierte la promesa temporal en una salida real.
1. Validar que la reserva esté `ACTIVE`.
2. Crear transacción de Salida (Issue) en `inventory_ledger` por la cantidad confirmada.
3. Actualizar `stock_balances`: 
   - `reserved_qty -= 2` (libera reserva)
   - `physical_qty -= 2` (consume físico)
   - `available_qty` se mantiene igual (ya fue deducido en el paso 1).
4. Marcar `reservations.status = COMPLETED`.

> [!NOTE]
> Si `actual_quantity_to_issue` < cantidad reservada (ej. cliente reservó 2, compró 1), la diferencia debe ser devuelta a `available_qty`.

---

### 2.3 Worker Asíncrono de Expiración (Cron / Celery Beat)

**RF:** RF-024 | **Lógica de Backend**

El sistema ejecutará un proceso en segundo plano (cada 1 minuto) buscando reservas expiradas:

```sql
SELECT id FROM reservations 
WHERE status = 'ACTIVE' 
  AND expires_at <= NOW();
```

Por cada reserva encontrada:
1. `reservations.status = EXPIRED`.
2. Retornar stock: `stock_balances.reserved_qty -= X`, `stock_balances.available_qty += X`.
3. Disparar Webhook (RF-032): `reservation.expired` para que el E-commerce sepa que el carrito perdió prioridad.

---

## 3. Tablas de Base de Datos Afectadas

| Tabla | Operación | RLS |
|-------|-----------|:---:|
| `reservations` | CRUD | ✅ |
| `stock_balances` | UPDATE | ✅ |

### Índices Requeridos

```sql
CREATE INDEX idx_reservations_tenant_status_exp ON reservations(tenant_id, status, expires_at);
```

---

## 4. Modelo Pydantic (Schemas Python)

```python
class ReservationItemInput(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    zone_id: UUID | None = None
    quantity: Decimal = Field(..., gt=0)

class ReservationCreate(BaseModel):
    reference_type: str = Field(..., max_length=50)
    reference_id: str = Field(..., max_length=100)
    expires_at: datetime | None = None
    items: list[ReservationItemInput] = Field(..., min_length=1)

class ReservationConfirm(BaseModel):
    actual_quantity_to_issue: Decimal = Field(..., gt=0)
    issue_reference: str
```
