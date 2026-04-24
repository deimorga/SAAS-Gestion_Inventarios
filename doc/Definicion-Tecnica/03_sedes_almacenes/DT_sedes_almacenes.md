# Definición Técnica — Módulo 03: Sedes y Almacenes

**Versión:** 1.0  
**Estado:** Borrador  
**Fecha:** 2026-04-24  
**RF Cubiertos:** RF-013 a RF-015  
**Prioridad:** P1  
**Autor:** Agente Antigravity (Arquitecto de Soluciones)

---

> [!IMPORTANT]
> Este módulo define la topología física y lógica donde residirá el inventario. Es prerequisito para cualquier transacción de entrada o salida.

## 1. Resumen de Endpoints

| # | Método | Endpoint | RF | Descripción | Scope |
|---|--------|----------|----|-------------|-------|
| 1 | `GET` | `/v1/warehouses` | RF-013 | Listar almacenes | `READ_WAREHOUSES` |
| 2 | `POST` | `/v1/warehouses` | RF-013 | Crear almacén | `MANAGE_WAREHOUSES` |
| 3 | `GET` | `/v1/warehouses/{id}` | RF-013 | Detalle de almacén | `READ_WAREHOUSES` |
| 4 | `PATCH` | `/v1/warehouses/{id}` | RF-013 | Actualizar almacén | `MANAGE_WAREHOUSES` |
| 5 | `GET` | `/v1/warehouses/{id}/zones` | RF-014 | Listar zonas del almacén | `READ_WAREHOUSES` |
| 6 | `POST` | `/v1/warehouses/{id}/zones` | RF-014 | Crear zona/bin | `MANAGE_WAREHOUSES` |
| 7 | `PATCH` | `/v1/zones/{zone_id}` | RF-014 | Actualizar estado/tipo de zona | `MANAGE_WAREHOUSES` |
| 8 | `GET` | `/v1/zones/{zone_id}` | RF-014 | Detalle de zona | `READ_WAREHOUSES` |

---

## 2. Contratos API Detallados

### 2.1 POST `/v1/warehouses` — Crear Almacén

**RF:** RF-013, RF-015 | **Tablas:** `warehouses`, `zones` (virtuales)

#### Request

```json
{
  "code": "BOG-NTE-01",
  "name": "Bodega Principal Bogotá Norte",
  "location_address": "Calle 170 # 67-89",
  "is_virtual": false,
  "timezone": "America/Bogota"
}
```

| Campo | Tipo | Requerido | Validación |
|-------|------|:---------:|------------|
| `code` | `string` | ✅ | Min 2, max 20. Único por tenant. Sin espacios. |
| `name` | `string` | ✅ | Min 1, max 100 |
| `location_address` | `string` | ❌ | Opcional |
| `is_virtual` | `bool` | ❌ | Default false |
| `timezone` | `string` | ❌ | Default hereda de tenant_config |

#### Response — `201 Created`

```json
{
  "id": "wh-uuid-new",
  "tenant_id": "tenant-uuid",
  "code": "BOG-NTE-01",
  "name": "Bodega Principal Bogotá Norte",
  "location_address": "Calle 170 # 67-89",
  "is_virtual": false,
  "is_active": true,
  "timezone": "America/Bogota",
  "created_at": "2026-04-24T10:00:00Z"
}
```

#### Lógica de Negocio Automática (RF-015)

Al crear un almacén (si `is_virtual = false`), el sistema debe crear automáticamente 3 zonas lógicas asociadas a este almacén:
1. `zone_type: RECEIVING` (Recepción temporal)
2. `zone_type: DISPATCH` (Zona de despacho)
3. `zone_type: QUARANTINE` (Zona de cuarentena/inspección)

Estas zonas automáticas aseguran que el almacén pueda operar con estados de inventario complejos desde el día 1.

---

### 2.2 GET `/v1/warehouses` — Listar Almacenes

**RF:** RF-013 | **Tablas:** `warehouses`

#### Query Parameters

| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `is_active` | `bool` | `true` | Filtrar activos/inactivos |
| `is_virtual` | `bool` | `null` | Filtrar físicos vs virtuales (tránsito) |

#### Response — `200 OK`

```json
{
  "data": [
    {
      "id": "wh-uuid-1",
      "code": "BOG-NTE-01",
      "name": "Bodega Principal Bogotá Norte",
      "is_virtual": false,
      "is_active": true
    },
    {
      "id": "wh-uuid-transit",
      "code": "TRANSIT-01",
      "name": "Almacén de Tránsito Global",
      "is_virtual": true,
      "is_active": true
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total_items": 2, "total_pages": 1 }
}
```

---

### 2.3 PATCH `/v1/warehouses/{id}` — Actualizar/Desactivar Almacén

**RF:** RF-013 | **Tablas:** `warehouses`, `stock_balances`

#### Request (parcial)

```json
{
  "name": "Bodega Principal Norte (Ampliación)",
  "is_active": false
}
```

#### Errores Críticos

| Código | Condición |
|--------|-----------|
| `409` | Intento de desactivar (`is_active: false`) un almacén que tiene saldo > 0 en `stock_balances` |

> [!WARNING]
> RN-013-2: Un almacén solo puede ser desactivado si **todo su inventario físico es cero** en todas sus zonas.

---

### 2.4 POST `/v1/warehouses/{id}/zones` — Crear Zona / Bin (Zonificación)

**RF:** RF-014 | **Tablas:** `zones`

#### Request

```json
{
  "code": "PASILLO-A-EST-01",
  "name": "Pasillo A - Estante 01",
  "zone_type": "STORAGE",
  "capacity_volume": 10.5,
  "capacity_weight": 500.0,
  "parent_zone_id": null
}
```

| Campo | Tipo | Requerido | Validación |
|-------|------|:---------:|------------|
| `code` | `string` | ✅ | Único dentro del almacén |
| `zone_type` | `enum` | ✅ | `RECEIVING`, `STORAGE`, `PICKING`, `DISPATCH`, `QUARANTINE`, `TRANSIT` |
| `capacity_volume` | `decimal` | ❌ | > 0 si se especifica |
| `capacity_weight` | `decimal` | ❌ | > 0 si se especifica |
| `parent_zone_id` | `uuid` | ❌ | Para jerarquías (Pasillo > Rack > Bin) |

#### Response — `201 Created`

```json
{
  "id": "zone-uuid-new",
  "warehouse_id": "wh-uuid-1",
  "code": "PASILLO-A-EST-01",
  "name": "Pasillo A - Estante 01",
  "zone_type": "STORAGE",
  "path": "PASILLO-A-EST-01",
  "is_active": true
}
```

---

### 2.5 PATCH `/v1/zones/{zone_id}` — Actualizar Zona

**RF:** RF-014 | **Tablas:** `zones`, `stock_balances`

#### Request

```json
{
  "zone_type": "QUARANTINE",
  "is_active": true
}
```

#### Lógica de Negocio

Si se cambia el `zone_type` de una zona que contiene stock, el estado del stock implícitamente cambia. Sin embargo, a nivel de backend, cambiar el tipo de una zona con stock activo puede requerir un proceso asíncrono para emitir eventos de re-valoración de disponibilidad si el tipo cambia de `STORAGE` (disponible) a `QUARANTINE` (no disponible para venta).

> [!CAUTION]
> RN-014-3: Si una zona tiene saldo físico > 0, cambiar su tipo de `STORAGE` a `QUARANTINE` reducirá el `available_qty` de esos productos. Esto debe validarse contra reservas activas (no se puede poner en cuarentena stock que ya está reservado).

---

## 3. Tablas de Base de Datos Afectadas

| Tabla | Endpoints | RLS |
|-------|-----------|:---:|
| `warehouses` | CRUD Almacenes | ✅ |
| `zones` | CRUD Zonas | ✅ |
| `stock_balances` | Read (Validación al desactivar) | ✅ |

### Índices Requeridos

```sql
-- warehouses
CREATE UNIQUE INDEX idx_warehouses_tenant_code ON warehouses(tenant_id, code);

-- zones
CREATE UNIQUE INDEX idx_zones_wh_code ON zones(warehouse_id, code);
CREATE INDEX idx_zones_tenant ON zones(tenant_id);
```

---

## 4. Modelo Pydantic (Schemas Python)

```python
class WarehouseCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20, pattern=r"^[A-Za-z0-9\-_]+$")
    name: str = Field(..., min_length=1, max_length=100)
    location_address: str | None = None
    is_virtual: bool = False
    timezone: str | None = None

class WarehouseResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    location_address: str | None
    is_virtual: bool
    is_active: bool
    timezone: str
    created_at: datetime

class ZoneType(str, Enum):
    RECEIVING = "RECEIVING"
    STORAGE = "STORAGE"
    PICKING = "PICKING"
    DISPATCH = "DISPATCH"
    QUARANTINE = "QUARANTINE"
    TRANSIT = "TRANSIT"

class ZoneCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    zone_type: ZoneType
    capacity_volume: Decimal | None = Field(None, gt=0)
    capacity_weight: Decimal | None = Field(None, gt=0)
    parent_zone_id: UUID | None = None

class ZoneResponse(BaseModel):
    id: UUID
    warehouse_id: UUID
    code: str
    name: str
    zone_type: ZoneType
    path: str
    is_active: bool
    capacity_volume: Decimal | None
    capacity_weight: Decimal | None
```
