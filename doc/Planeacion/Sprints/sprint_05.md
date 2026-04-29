# Sprint 5 — Trazabilidad Avanzada

**Fecha Inicio:** 2026-04-28
**Fecha Fin Real:** 2026-04-28
**Estado:** ✅ Completado

---

## 🎯 Objetivo del Sprint

Completar el MVP con los módulos de trazabilidad avanzada. El sprint cubre: (1) **Directorio de Proveedores** y costos de reposición para cerrar el ciclo de compras, (2) **Kits/Combos (BOM)** para productos compuestos, (3) **Trazabilidad por Lotes y Seriales** con control de vencimiento, (4) **Zonificación (Bins/Slots)** con bloqueos de ubicación, (5) **Re-empaque** como tipo transaccional nuevo, y (6) **Allocation por Canal** para reservas segmentadas.

---

## 📋 Items del Sprint

| ID | Requerimiento | Tarea | Estado | Notas |
|---|---|---|---|---|
| T-501 | RF-011 | Directorio de Proveedores — CRUD + asociación a productos | ✅ Completado | Migración 008; tablas `suppliers` + `supplier_products` |
| T-502 | RF-012 | Costos de Reposición — precios de compra por proveedor | ✅ Completado | Depende T-501; columnas en `supplier_products` |
| T-503 | RF-009 | Kits/Combos — CRUD de componentes BOM | ✅ Completado | Tabla `kit_components` ya en migración 002 |
| T-504 | RF-010 | Lotes y Seriales — registro y validación | ✅ Completado | Migración 009; tablas `batches` + `serial_numbers` |
| T-505 | RF-014 | Zonificación Bins/Slots — CRUD de ubicaciones | ✅ Completado | Migración 010; tabla `bins` |
| T-506 | RF-015 | Bloqueos de Ubicación — lock/unlock de bins | ✅ Completado | Depende T-505; tabla `location_locks` |
| T-507 | RF-021 | Re-empaque — conversión de presentación | ✅ Completado | Nuevo tipo REPACK en motor transaccional |
| T-508 | RF-023 | Control de Vencimiento — alertas de caducidad | ✅ Completado | Depende T-504; endpoint GET /reports/expiring |
| T-509 | RF-024 | Validación de Seriales — verificar estado antes de issue | ✅ Completado | Depende T-504; endpoint GET /serials/{sn}/status |
| T-510 | RF-028 | Allocation por Canal — reservas segmentadas | ✅ Completado | Migración 011; tabla `channel_allocations` |

---

## 🗄️ Modelo de Datos Nuevo

### Migración 008 — Suppliers

#### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `suppliers` | Directorio de proveedores del tenant | ✅ |
| `supplier_products` | Asociación proveedor-producto con costo y tiempo de entrega | ✅ |

### Migración 009 — Lotes y Seriales

#### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `batches` | Lotes de fabricación/recepción con fecha de vencimiento | ✅ |
| `serial_numbers` | Números de serie individuales por producto | ✅ |

### Migración 010 — Zonificación y Bloqueos

#### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `bins` | Ubicaciones físicas (slots) dentro de una zona | ✅ |
| `location_locks` | Bloqueos temporales de bins o zonas completas | ✅ |

### Migración 011 — Allocation por Canal

#### Tablas nuevas

| Tabla | Descripción | RLS |
|---|---|---|
| `channel_allocations` | Cuotas de inventario reservadas por canal (WEB, POS, B2B, etc.) | ✅ |

---

## 🌐 Endpoints Nuevos

### Proveedores — `/v1/suppliers`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/suppliers` | RF-011 | Crear proveedor |
| `GET` | `/v1/suppliers` | RF-011 | Listar proveedores |
| `GET` | `/v1/suppliers/{id}` | RF-011 | Detalle de proveedor |
| `PATCH` | `/v1/suppliers/{id}` | RF-011 | Actualizar proveedor |
| `DELETE` | `/v1/suppliers/{id}` | RF-011 | Desactivar proveedor |
| `POST` | `/v1/suppliers/{id}/products` | RF-012 | Asociar producto con costo de reposición |
| `GET` | `/v1/suppliers/{id}/products` | RF-012 | Listar productos del proveedor |
| `PATCH` | `/v1/suppliers/{id}/products/{pid}` | RF-012 | Actualizar costo/lead time |
| `DELETE` | `/v1/suppliers/{id}/products/{pid}` | RF-012 | Eliminar asociación |

### Kits/BOM — sub-recurso de `/v1/products`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `GET` | `/v1/products/{id}/components` | RF-009 | Listar componentes del kit |
| `POST` | `/v1/products/{id}/components` | RF-009 | Agregar componente al kit |
| `DELETE` | `/v1/products/{id}/components/{cid}` | RF-009 | Eliminar componente del kit |

### Lotes y Seriales — `/v1/batches`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/batches` | RF-010 | Crear lote |
| `GET` | `/v1/batches` | RF-010 | Listar lotes (filtro por producto) |
| `GET` | `/v1/batches/{id}` | RF-010 | Detalle de lote |
| `POST` | `/v1/batches/{id}/serials` | RF-010 | Registrar seriales en el lote |
| `GET` | `/v1/batches/{id}/serials` | RF-010 | Listar seriales del lote |
| `GET` | `/v1/serials/{serial_number}/status` | RF-024 | Validar estado de un serial |

### Zonificación — sub-recurso de `/v1/warehouses`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `GET` | `/v1/warehouses/{id}/zones/{zid}/bins` | RF-014 | Listar bins de la zona |
| `POST` | `/v1/warehouses/{id}/zones/{zid}/bins` | RF-014 | Crear bin en la zona |
| `PATCH` | `/v1/warehouses/bins/{bid}` | RF-014 | Actualizar bin |
| `DELETE` | `/v1/warehouses/bins/{bid}` | RF-014 | Desactivar bin |
| `POST` | `/v1/warehouses/bins/{bid}/locks` | RF-015 | Bloquear bin |
| `DELETE` | `/v1/warehouses/bins/{bid}/locks` | RF-015 | Desbloquear bin |

### Motor — `/v1/transactions`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/transactions/repacks` | RF-021 | Re-empaque (conversión de presentación) |

### Reportes — `/v1/reports`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `GET` | `/v1/reports/expiring` | RF-023 | Lotes por vencer en N días |

### Channel Allocation — `/v1/channel-allocations`

| Método | Endpoint | RF | Descripción |
|---|---|---|---|
| `POST` | `/v1/channel-allocations` | RF-028 | Definir cuota por canal |
| `GET` | `/v1/channel-allocations` | RF-028 | Listar cuotas activas |
| `PATCH` | `/v1/channel-allocations/{id}` | RF-028 | Actualizar cuota |
| `DELETE` | `/v1/channel-allocations/{id}` | RF-028 | Eliminar cuota |

---

## 🚦 Criterios de Aceptación (DoD)

| Criterio | Umbral | Estado |
|----------|--------|--------|
| Cobertura global ≥80% | ≥80% | ✅ 92% |
| 0 errores `ruff` | `All checks passed!` | ✅ |
| 0 errores `mypy` | `Success: no issues found` | ✅ 92 archivos |
| RLS en tablas nuevas | suppliers, supplier_products, batches, serial_numbers, bins, location_locks, channel_allocations | ✅ |
| Convención DOC-001 aplicada | Todos los endpoints nuevos | ✅ |

## 📊 Métricas Finales

| Métrica | Sprint 4 | Sprint 5 |
|---------|----------|----------|
| Tests totales | 154 | **208** |
| Cobertura | 91% | **92%** |
| Ruff errors | 0 | **0** |
| Mypy errors | 0 | **0** |
| Source files | 75 | **92** |
| Endpoints totales | ~52 | **~76** |
| Migraciones | 007 | **008–011** |
