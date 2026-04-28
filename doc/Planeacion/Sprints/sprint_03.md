# Sprint 3 — Reportes, Reservas y Documentación API

**Fecha Inicio:** 2026-04-29
**Fecha Fin Estimada:** 2026-05-12
**Estado:** ⏳ Pendiente

---

## 🎯 Objetivo del Sprint

Implementar el módulo de reportes operativos (Kardex, Valoración Contable, Alertas de Stock), el motor de reservas temporales con expiración automática, y la documentación pública de la API (OpenAPI enriquecido + exportación estática). Con este sprint se completa la visibilidad analítica del inventario y se habilita la integración con sistemas de comercio que necesitan reservar stock antes de confirmar pedidos.

---

## 📋 Items del Sprint

| ID | Requerimiento | Tarea | Estado | Notas |
|---|---|---|---|---|
| T-301 | RF-029 | Kardex Histórico (`GET /v1/reports/kardex`) | ⏳ Pendiente | Movimientos paginados con balance running |
| T-302 | RF-032 | Valoración Contable (`GET /v1/reports/valuation`) | ⏳ Pendiente | SUM(qty × cpp) por producto; total consolidado |
| T-303 | RF-030 | Balance Snapshots (`POST/GET /v1/reports/valuation/snapshots`) | ⏳ Pendiente | FastAPI BackgroundTask; tabla `valuation_snapshots`; 202 Accepted |
| T-304 | RF-031 | Alertas Stock Bajo (`GET /v1/reports/low-stock`) | ⏳ Pendiente | `available_qty ≤ reorder_point`; campo ya existe en `products` |
| T-305 | RF-025 | Soft Reservations + TTL (`POST/GET /v1/reservations`) | ⏳ Pendiente | OCC en `stock_balances`; nuevas tablas `reservations` + `reservation_items` |
| T-306 | RF-026 | Hard Commitment (`POST /v1/reservations/{id}/confirm`) | ⏳ Pendiente | Convierte reserva en Issue; libera `reserved_qty` sobrante si qty < reservada |
| T-307 | RF-027 | Auto-Expiration (`POST /v1/reservations/{id}/cancel` + background) | ⏳ Pendiente | Startup task periódica; devuelve `available_qty`; status → `EXPIRED` |
| T-308 | DOC-001 | Documentación API OpenAPI | ⏳ Pendiente | Ver sección Documentación API más abajo |

---

## 🗄️ Modelo de Datos Nuevo (migración 004)

### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `reservations` | Cabecera de cada reserva (`ACTIVE` / `COMPLETED` / `CANCELLED` / `EXPIRED`) | ✅ |
| `reservation_items` | Líneas de producto por reserva (product, zone, qty reservada, qty confirmada) | ✅ |
| `valuation_snapshots` | Fotos contables de cierre de mes, append-only | ✅ |

### DDL referencia

```sql
-- reservations
CREATE TABLE reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    reference_type VARCHAR(50) NOT NULL,
    reference_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_reservations_tenant_status_exp ON reservations(tenant_id, status, expires_at);
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON reservations
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- reservation_items
CREATE TABLE reservation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id UUID NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id),
    zone_id UUID NOT NULL REFERENCES zones(id),
    quantity DECIMAL(18,4) NOT NULL CHECK (quantity > 0),
    confirmed_qty DECIMAL(18,4) NOT NULL DEFAULT 0
);
ALTER TABLE reservation_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservation_items FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON reservation_items
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- valuation_snapshots
CREATE TABLE valuation_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period VARCHAR(20) NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id),
    snapshot_qty DECIMAL(18,4) NOT NULL,
    snapshot_cpp DECIMAL(18,4) NOT NULL,
    total_value DECIMAL(18,4) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_snapshots_tenant_period ON valuation_snapshots(tenant_id, period);
ALTER TABLE valuation_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE valuation_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON valuation_snapshots
    USING (tenant_id::text = current_setting('app.current_tenant', true));
```

---

## 🌐 Endpoints Nuevos

### Reportes — `GET /v1/reports/...`

| Método | Endpoint | RF | Query Params principales |
|---|---|---|---|
| `GET` | `/v1/reports/kardex` | RF-029 | `product_id` (req), `warehouse_id`, `date_from`, `date_to`, `page`, `page_size` |
| `GET` | `/v1/reports/valuation` | RF-032 | `category_id`, `warehouse_id` |
| `POST` | `/v1/reports/valuation/snapshots` | RF-030 | Body: `{ period, description }` → 202 Accepted |
| `GET` | `/v1/reports/valuation/snapshots` | RF-030 | `period` |
| `GET` | `/v1/reports/low-stock` | RF-031 | `warehouse_id`, `category_id`, `page`, `page_size` |

### Reservas — `/v1/reservations`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/reservations` | RF-025 | Crear reserva; `reserved_qty += qty`, `available_qty -= qty` (OCC) |
| `GET` | `/v1/reservations` | RF-025 | Listar reservas activas del tenant |
| `GET` | `/v1/reservations/{id}` | RF-025 | Detalle de reserva con sus items |
| `POST` | `/v1/reservations/{id}/confirm` | RF-026 | Convierte en Issue; `physical_qty -= qty`, `reserved_qty -= qty` |
| `POST` | `/v1/reservations/{id}/cancel` | RF-027 | Cancelación explícita; `reserved_qty -= qty`, `available_qty += qty` |

---

## 📖 Documentación API (DOC-001)

### Objetivo
Publicar la documentación de la API de forma segura y accesible para integradores externos, sin exponer `/docs`/`/redoc` en producción.

### Plan de implementación

| Paso | Actividad | Archivos afectados |
|---|---|---|
| 1 | Enriquecer schemas Pydantic con `description` y `json_schema_extra` (examples) | `app/schemas/*.py` |
| 2 | Agregar `summary`, `description` y `responses` a todos los endpoints | `app/api/v1/endpoints/*.py` |
| 3 | Configurar metadata de la app: `title`, `version`, `description`, `contact`, `license_info` | `app/main.py` |
| 4 | Control de `/docs` y `/redoc` via `ENABLE_SWAGGER` en env (default `false` en prod) | `app/core/config.py` + `app/main.py` |
| 5 | Script para exportar `openapi.json` estático | `scripts/export_openapi.py` |

### Comportamiento por entorno

| Entorno | `/docs` | `/redoc` | `openapi.json` |
|---|---|---|---|
| Development | ✅ Habilitado | ✅ Habilitado | ✅ Disponible |
| Staging | ✅ Habilitado | ✅ Habilitado | ✅ Disponible |
| Production | ❌ Deshabilitado | ❌ Deshabilitado | ✅ Exportado a `doc/api/openapi.json` en CI |

---

## 🔑 Dependencias y Patrones de Implementación

### Patrones que aplican de sprints anteriores

- `UUID(as_uuid=False)` en todos los modelos SQLAlchemy nuevos.
- OCC de 3 reintentos en operaciones sobre `stock_balances` (reservas y cancellations).
- RLS: todas las tablas nuevas con `ENABLE ROW LEVEL SECURITY` + `FORCE` + política `tenant_isolation`.
- Tests helpers en `conftest.py`: extender `_create_product_simple` para incluir `reorder_point`.

### Nuevos patrones a introducir

- **FastAPI BackgroundTask**: para snapshot de valoración (responde 202 de inmediato, procesa en background).
- **Startup periodic task**: livianas comprobaciones de reservas expiradas con `asyncio.create_task` en `startup`.

---

## 🚦 Criterios de Aceptación (DoD)

| Criterio | Umbral | Estado |
|----------|--------|--------|
| Cobertura global ≥80% | ≥80% | ⏳ |
| 0 errores `ruff` | `All checks passed!` | ⏳ |
| 0 errores `mypy` | `Success: no issues found` | ⏳ |
| RLS validado en tablas nuevas | `reservations`, `reservation_items`, `valuation_snapshots` | ⏳ |
| OCC aplicado en reservas | Máx 3 reintentos; 409 si se agota | ⏳ |
| Snapshot genera en background | 202 Accepted; procesa sin bloquear | ⏳ |
| Auto-expiry devuelve stock | `available_qty` correcto tras expiración | ⏳ |
| OpenAPI exportado sin errores | `scripts/export_openapi.py` ejecutable | ⏳ |
| `/docs` deshabilitado en prod | `ENABLE_SWAGGER=false` → 404 en `/docs` | ⏳ |
