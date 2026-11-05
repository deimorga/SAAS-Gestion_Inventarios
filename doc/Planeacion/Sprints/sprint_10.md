# Sprint 10 — Trazabilidad de Lotes, Proveedores y Ubicaciones

**Fecha Inicio:** 2026-11-04
**Fecha Fin Estimada:** 2026-11-05 (desarrollo); despliegue por definir
**Responsable:** Cristian Anacona
**Revisión y despliegue:** Deiby Moreno
**Estado:** 🟡 Desarrollo terminado y probado en local — pendiente de commit, merge y despliegue

**Definición funcional:** [RF_trazabilidad_lotes_ubicaciones.md](../../Funcional/mejorado/10_trazabilidad_lotes_ubicaciones/RF_trazabilidad_lotes_ubicaciones.md) (RF-053 a RF-061)
**Definición técnica:** [DT_trazabilidad_lotes_ubicaciones.md](../../Definicion-Tecnica/10_trazabilidad_lotes_ubicaciones/DT_trazabilidad_lotes_ubicaciones.md)
**Contrato para Appits:** [trazabilidad_lotes_ubicaciones.md](../../integracion/trazabilidad_lotes_ubicaciones.md)

---

## 🎯 Objetivo del Sprint

Que Appits sepa **dónde está** cada repuesto (bodega → zona → ubicación), **de qué proveedor** vino cada
lote y **en qué orden de servicio** se usó, sin cambiar ninguna de sus llamadas actuales.

**Contexto:** el saldo se llevaba por producto + zona, el lote no tenía proveedor y las reservas no
indicaban de qué lote salían. Al implementarlo aparecieron tres fallos silenciosos (una confirmación que
descontaba de todos los saldos de la zona, un `GET /v1/ledger` que daba `500`, y confirmar más de lo
reservado) que se corrigieron de paso. En el portal se aprovechó para unificar Productos y Stock y
rediseñar el estilo.

---

## 🛡️ Condiciones (obligatorias)

Definidas por el solicitante. Detalle en la [definición funcional](../../Funcional/mejorado/10_trazabilidad_lotes_ubicaciones/RF_trazabilidad_lotes_ubicaciones.md#condiciones-del-requerimiento-obligatorias).

- **C-1** — Todo campo nuevo es opcional.
- **C-2** — Ningún campo existente cambia de nombre ni de tipo; las respuestas conservan sus campos.
- **C-3** — Sin pantallas nuevas en el portal admin.
- **C-4** — El ledger es inmutable.
- **C-5** — Los ajustes conservan `lot_number` y `reason`.
- **C-6** — No se toca el repo `SAAS-Gestion_Talleres`.
- **C-7** — Sin commit ni push hasta que el responsable lo apruebe.
- **C-8** — Identidad del lote = producto + proveedor + número.

## 👥 Responsabilidades

| Quién | Qué |
|---|---|
| **Cristian Anacona** | Desarrollo, tests y documentación de T-1001 a T-1014, en local, con Claude Code |
| **Deiby Moreno** | Revisión y merge, validación en staging, despliegue a producción y aviso a Appits (T-1015, T-1016) |

---

## 📋 Items del Sprint

Todos asignados a **Cristian Anacona**, salvo T-1015 y T-1016. Tamaño: S ≈ medio día · M ≈ 1–2 días · L ≈ 3+ días.

| ID | Área | Tarea | RF | Tamaño | Depende de | Estado |
|----|------|-------|----|--------|-----------|--------|
| T-1001 | Backend | Migración 015: columnas, índices únicos con `COALESCE`, `reservation_allocations`, `document_sequences`, relleno de entradas históricas bajo RLS | RF-053 a RF-058 | M | — | ✅ Hecho |
| T-1002 | Backend | Modelos y schemas: bin, proveedor, `document_number`, asignaciones; `transaction_id` opcional | RF-053 a RF-058 | S | T-1001 | ✅ Hecho |
| T-1003 | Backend | `traceability.py`: validación de bin/proveedor, lote obligatorio, `ensure_batch`, consecutivo | RF-053, 054, 057, 058 | M | T-1001 | ✅ Hecho |
| T-1004 | Backend | `inventory.py`: entradas, salidas, traslados y ajustes con bin, proveedor y lote; `409` si el lote es ambiguo | RF-053, 054, 057 | L | T-1002, T-1003 | ✅ Hecho |
| T-1005 | Backend | Lotes: `supplier_id` y unicidad por producto + proveedor (`services/batch.py`) | RF-054 | S | T-1001 | ✅ Hecho |
| T-1006 | Backend | Reservas reescritas: asignaciones, FEFO → FIFO, `FOR UPDATE`, confirmar por lote, cancelar y expirar, rama legacy | RF-055, RF-061 | L | T-1004 | ✅ Hecho |
| T-1007 | Backend | `main.py`: el bucle de expiración llama a `expire_reservation` | RF-061 | S | T-1006 | ✅ Hecho |
| T-1008 | Backend | Filtros de saldos y ledger y campos nuevos de respuesta | RF-056 | M | T-1004 | ✅ Hecho |
| T-1009 | Backend | `GET /admin/tenants/{id}/suppliers` | RF-056 | S | — | ✅ Hecho |
| T-1010 | Tests | `test_lot_location_traceability.py` (27): compatibilidad, bins, proveedores, reservas, concurrencia, filtros, aislamiento | Todos | L | Cada tarea | ✅ Hecho |
| T-1011 | Portal | Tema y rediseño: `theme.py`, barra lateral, tarjetas, píldoras, categorías con ícono | RF-060 | L | — | ✅ Hecho |
| T-1012 | Portal | Productos con existencias (opción 1): desglose por almacén/zona/ubicación/lote/proveedor, ajuste por fila, campo Lote | RF-059 | L | T-1008, T-1009 | ✅ Hecho |
| T-1013 | Docs | Contrato de integración para Appits y `CLAUDE.md` (15 migraciones, módulos y conteo de tests, deuda conocida) | — | S | T-1010 | ✅ Hecho |
| T-1014 | Docs | RF, DT y sprint del módulo 10; notas en RF-016, RF-025, RF-026 y RF-027 | — | S | T-1013 | ✅ Hecho |
| T-1015 | Despliegue | **(Deiby)** Revisar, staging → prod y renumerar la migración del módulo 09 a 016 al implementarla. `origin/main` ya está integrado en la rama (2026-11-05) | — | M | T-1010 | ⬜ Pendiente |
| T-1016 | Integración | **(Deiby)** Avisar a Appits de los tres cambios de comportamiento y enviarle el contrato | RF-061 | S | T-1015 | ⬜ Pendiente |

### Backlog derivado (no está en este sprint)

| ID | Tarea | Por qué |
|----|-------|---------|
| T-1017 | Conteos cíclicos por lote y bin (`cycle_count.py`) | Con varios lotes o bins en la zona fijan todas las filas al valor contado (DT §10) |
| T-1018 | Portal: capturar y mostrar ubicación, proveedor y vencimiento | Hoy solo se asignan por API |
| T-1019 | Corregir el dominio en `doc/integracion/api_scopes.md` | Usa `api.micronuba.com` |

---

## 📁 Archivos del sprint (24)

El conjunto de cambios sin commitear a 2026-11-05 son 24 archivos: 19 modificados y 5 nuevos.
Estos tres documentos y las notas en los RF anteriores se suman a ellos.

| # | Archivo | Qué cambió |
|---|---|---|
| 1 | `core_backend/alembic/versions/015_lot_location_traceability.py` *(nuevo)* | Migración 015 |
| 2 | `core_backend/app/services/traceability.py` *(nuevo)* | Validaciones compartidas y consecutivo |
| 3 | `core_backend/tests/test_lot_location_traceability.py` *(nuevo)* | 27 tests |
| 4 | `doc/integracion/trazabilidad_lotes_ubicaciones.md` *(nuevo)* | Contrato para Appits |
| 5 | `web_frontend/app/theme.py` *(nuevo)* | Tema del portal |
| 6 | `core_backend/app/models/__init__.py` | Exporta `ReservationAllocation` |
| 7 | `core_backend/app/models/batch.py` | `supplier_id` |
| 8 | `core_backend/app/models/inventory_ledger.py` | `bin_id`, `supplier_id` |
| 9 | `core_backend/app/models/reservation.py` | Campos del ítem y `ReservationAllocation` |
| 10 | `core_backend/app/models/stock_balance.py` | `bin_id`, `supplier_id` |
| 11 | `core_backend/app/models/transaction.py` | `document_number` |
| 12 | `core_backend/app/schemas/batch.py` | `supplier_id` |
| 13 | `core_backend/app/schemas/inventory.py` | Campos de entrada y respuesta; `transaction_id` opcional |
| 14 | `core_backend/app/schemas/reservation.py` | Lote, bin, proveedor y `allocations` |
| 15 | `core_backend/app/services/batch.py` | Unicidad por proveedor |
| 16 | `core_backend/app/services/inventory.py` | Movimientos, filtros y consecutivo |
| 17 | `core_backend/app/services/reservation.py` | Reescrito |
| 18 | `core_backend/app/services/supplier.py` | `is_active: bool \| None` |
| 19 | `core_backend/app/api/v1/endpoints/inventory.py` | Filtros de saldos y ledger |
| 20 | `core_backend/app/api/admin/endpoints/admin_products.py` | `GET /admin/tenants/{id}/suppliers` |
| 21 | `core_backend/app/main.py` | Expiración con `expire_reservation` |
| 22 | `web_frontend/app/api.py` | `list_stock` paginado, `list_suppliers` |
| 23 | `web_frontend/app/main.py` | Rediseño y Productos con existencias |
| 24 | `CLAUDE.md` | Sección 2026-11-04, 15 migraciones, módulos y conteo de tests |

### Orden sugerido para revisar

1. **T-1001** y los modelos: es la base y lo que más cuesta deshacer.
2. **T-1006** (reservas): el cambio de mayor superficie; leer junto a sus 12 tests.
3. **T-1004** y **T-1003**: reglas de bin, proveedor y lote.
4. **T-1008** y **T-1009**: filtros y campos de respuesta.
5. Portal (**T-1011**, **T-1012**): se puede revisar aparte, no toca el API de clientes.

---

## ✅ Definición de Hecho (DoD)

- [x] Todos los criterios de aceptación HU-LOT-001 a HU-LOT-006 cubiertos por tests.
- [x] `ruff check app/` y `mypy app/` sin errores; suite completa en verde en local: `373 passed, 1 skipped` antes de integrar `origin/main` y **`386 passed, 1 skipped`** después (suma los 13 tests nuevos de `origin/main`).
- [x] Los 346 tests anteriores pasan sin modificarse (compatibilidad, C-1).
- [x] Migración probada en ciclo `down` → `up` con datos existentes.
- [x] El ledger solo recibe registros nuevos (C-4); sin pantallas nuevas (C-3).
- [x] La concurrencia de reservas se prueba de forma determinista y se verificó por mutación.
- [x] `origin/main` integrado en la rama (2026-11-05); conflicto de `web_frontend/app/main.py` resuelto.
- [ ] Revisado y mezclado por Deiby, con la migración del módulo 09 renumerada a 016.
- [ ] Probado de punta a punta en staging con el flujo de Appits.
- [ ] Appits avisado de los cambios de comportamiento.
- [ ] Desplegado en prod por Deiby, con aviso a infra del commit y la hora.
- [ ] Las tres ramas (`main`, `staging`, `develop`) en el mismo commit al cerrar el sprint.

---

## ⚠️ Riesgos

| Riesgo | Mitigación |
|---|---|
| ~~Conflicto con `origin/main`~~ en `web_frontend/app/main.py`: el límite de intentos de login se añadió en el `page_login` que este sprint rediseñó | **Resuelto el 2026-11-05** al integrar `origin/main`: se conservó el diseño nuevo y las líneas de login (`request`, IP del navegador, `client_ip`, mensaje `429`). Confirmado con la suite completa tras la mezcla: `386 passed, 1 skipped`, incluido `test_login_throttle.py` |
| **Choque de numeración de migraciones:** el módulo 09 documenta «014» y aquí 014 es sedes y 015 es este módulo | Renombrar la de usuarios a 016 con `down_revision = "015"` antes de implementarla |
| Appits hace entradas sin lote de productos con `track_lots = true` | Avisarles antes de producción; empezarán a recibir `422` (RF-061 #1) |
| La 015 numera las entradas históricas en la misma migración | Medir en staging; respaldar antes de prod |
| Bajar la 015 después de usarla falla o pierde datos (DT §6.3) | Tratarla como migración de ida: la reversa solo sin stock con bin o proveedor distinto |
| `services/reservation.py` se reescribió entero | Revisión dedicada y 12 tests específicos; el cambio de concurrencia se verificó por mutación |
| Los conteos cíclicos siguen operando por producto + zona | Registrado como T-1017; avisar si el cliente usa conteos con varios lotes por zona |
