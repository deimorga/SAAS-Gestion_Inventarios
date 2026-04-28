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
Publicar la documentación de la API de forma segura y accesible para integradores externos, sin exponer `/docs`/`/redoc` en producción. La documentación cubre **todos los endpoints existentes (Sprint 1 y 2) y todos los que se implementen en adelante**. A partir de este sprint, documentar cada endpoint es parte del DoD de cada tarea.

---

### Alcance — Endpoints a documentar (Sprint 1 + Sprint 2)

#### Gobierno y Seguridad (`auth`, `tenants`, `api-keys`, `audit`)

| Método | Endpoint | Sprint |
|---|---|---|
| `POST` | `/v1/auth/login` | 1 |
| `POST` | `/v1/auth/refresh` | 1 |
| `POST` | `/v1/auth/logout` | 1 |
| `GET` | `/v1/tenants/me` | 1 |
| `PATCH` | `/v1/tenants/me` | 1 |
| `GET` | `/v1/tenants/me/policy` | 1 |
| `PATCH` | `/v1/tenants/me/policy` | 1 |
| `GET` | `/v1/api-keys` | 1 |
| `POST` | `/v1/api-keys` | 1 |
| `DELETE` | `/v1/api-keys/{id}` | 1 |
| `GET` | `/v1/audit-logs` | 1 |

#### Catálogo (`products`, `categories`, `uom`)

| Método | Endpoint | Sprint |
|---|---|---|
| `GET` | `/v1/products` | 1 |
| `POST` | `/v1/products` | 1 |
| `GET` | `/v1/products/{id}` | 1 |
| `PATCH` | `/v1/products/{id}` | 1 |
| `DELETE` | `/v1/products/{id}` | 1 |
| `GET` | `/v1/products/{id}/uoms` | 1 |
| `POST` | `/v1/products/{id}/uoms` | 1 |
| `DELETE` | `/v1/products/{id}/uoms/{uom_id}` | 1 |
| `GET` | `/v1/categories` | 1 |
| `POST` | `/v1/categories` | 1 |
| `GET` | `/v1/categories/{id}` | 1 |
| `PATCH` | `/v1/categories/{id}` | 1 |
| `DELETE` | `/v1/categories/{id}` | 1 |

#### Almacenes y Zonas (`warehouses`)

| Método | Endpoint | Sprint |
|---|---|---|
| `GET` | `/v1/warehouses` | 2 |
| `POST` | `/v1/warehouses` | 2 |
| `GET` | `/v1/warehouses/{id}` | 2 |
| `PATCH` | `/v1/warehouses/{id}` | 2 |
| `GET` | `/v1/warehouses/{id}/zones` | 2 |
| `POST` | `/v1/warehouses/{id}/zones` | 2 |
| `GET` | `/v1/warehouses/zones/{zone_id}` | 2 |
| `PATCH` | `/v1/warehouses/zones/{zone_id}` | 2 |

#### Motor Transaccional (`transactions`, `stock`, `ledger`)

| Método | Endpoint | Sprint |
|---|---|---|
| `POST` | `/v1/transactions/receipts` | 2 |
| `POST` | `/v1/transactions/issues` | 2 |
| `POST` | `/v1/transactions/transfers` | 2 |
| `POST` | `/v1/transactions/adjustments` | 2 |
| `GET` | `/v1/stock/balances` | 2 |
| `GET` | `/v1/ledger` | 2 |

**Total endpoints existentes a documentar: ~37**

---

### Convención de Documentación (aplica a Sprint 3 en adelante)

Todo endpoint nuevo DEBE incluir en el momento de su implementación:

#### 1. En el decorador FastAPI

```python
@router.post(
    "/receipts",
    summary="Registrar entrada de mercancía",
    description="Crea una transacción de tipo RECEIPT. Actualiza stock_balances, recalcula CPP y registra en inventory_ledger.",
    response_description="Transacción creada con items procesados",
    status_code=201,
    responses={
        409: {"description": "Stock insuficiente o conflicto de concurrencia (OCC agotado)"},
        422: {"description": "Datos de entrada inválidos"},
    },
)
```

#### 2. En los schemas Pydantic

```python
class ReceiptItem(BaseModel):
    product_id: str = Field(..., description="UUID del producto", examples=["550e8400-e29b-41d4-a716-446655440000"])
    quantity: Decimal = Field(..., gt=0, description="Cantidad a recibir (mayor que 0)", examples=[10.5])
    unit_cost: Decimal = Field(..., gt=0, description="Costo unitario en moneda local", examples=[42500.00])

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "quantity": 10.5,
                "unit_cost": 42500.00,
            }
        }
    )
```

#### 3. En `app/main.py` — metadata de la app

```python
app = FastAPI(
    title="MicroNuba Inventory API",
    version="1.0.0",
    description="API de gestión de inventarios multi-tenant. ...",
    contact={"name": "MicroNuba", "email": "api@micronuba.com"},
    license_info={"name": "Propietario"},
    docs_url="/docs" if settings.ENABLE_SWAGGER else None,
    redoc_url="/redoc" if settings.ENABLE_SWAGGER else None,
)
```

---

### Plan de implementación (este sprint)

| Paso | Actividad | Archivos afectados |
|---|---|---|
| 1 | Configurar metadata de la app + control de `/docs`/`/redoc` por env | `app/main.py`, `app/core/config.py` |
| 2 | Enriquecer schemas Sprint 1 (auth, tenant, api-keys, catalog) con `description` + `examples` | `app/schemas/auth.py`, `tenant.py`, `api_key.py`, `catalog.py` |
| 3 | Enriquecer schemas Sprint 2 (warehouse, inventory) | `app/schemas/warehouse.py`, `inventory.py` |
| 4 | Agregar `summary`/`description`/`responses` a endpoints Sprint 1 | `app/api/v1/endpoints/auth.py`, `tenant.py`, `api_keys.py`, `audit_logs.py`, `categories.py`, `products.py` |
| 5 | Agregar `summary`/`description`/`responses` a endpoints Sprint 2 | `app/api/v1/endpoints/warehouses.py`, `inventory.py` |
| 6 | Documentar endpoints Sprint 3 al implementarlos (T-301 → T-307) | `app/api/v1/endpoints/reports.py`, `reservations.py` |
| 7 | Script de exportación `scripts/export_openapi.py` | `scripts/export_openapi.py` |

### Comportamiento por entorno

| Entorno | `/docs` | `/redoc` | `openapi.json` |
|---|---|---|---|
| Development | ✅ Habilitado | ✅ Habilitado | ✅ Disponible en `/openapi.json` |
| Staging | ✅ Habilitado | ✅ Habilitado | ✅ Disponible en `/openapi.json` |
| Production | ❌ Deshabilitado | ❌ Deshabilitado | ✅ Exportado a `doc/api/openapi.json` vía `scripts/export_openapi.py` |

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
| **Todos los endpoints S1+S2 documentados** | `summary` + `description` + `responses` + examples en schemas | ⏳ |
| **Todos los endpoints S3 documentados al implementarse** | Convención DOC-001 aplicada desde la primera línea de código | ⏳ |
| OpenAPI exportado sin errores | `scripts/export_openapi.py` ejecutable | ⏳ |
| `/docs` deshabilitado en prod | `ENABLE_SWAGGER=false` → 404 en `/docs` | ⏳ |

> **Regla a partir de Sprint 3:** Ningún endpoint nuevo se considera terminado sin su documentación OpenAPI (summary, description, responses, examples en el schema). Esto aplica a todos los sprints futuros.
