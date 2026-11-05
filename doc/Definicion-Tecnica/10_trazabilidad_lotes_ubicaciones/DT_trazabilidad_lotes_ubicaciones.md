# Definición Técnica — Módulo 10: Trazabilidad de Lotes, Proveedores y Ubicaciones

**Versión:** 1.0
**Estado:** ✅ Implementado y probado en local — pendiente de commit, merge y despliegue
**Fecha:** 2026-11-05 (implementado el 2026-11-04)
**RF Cubiertos:** RF-053 a RF-061 — [RF_trazabilidad_lotes_ubicaciones.md](../../Funcional/mejorado/10_trazabilidad_lotes_ubicaciones/RF_trazabilidad_lotes_ubicaciones.md)
**Responsable de desarrollo:** Cristian Anacona
**Sprint:** Sprint 10 — [sprint_10.md](../../Planeacion/Sprints/sprint_10.md)
**Contrato con ejemplos para Appits:** [trazabilidad_lotes_ubicaciones.md](../../integracion/trazabilidad_lotes_ubicaciones.md)

---

> [!IMPORTANT]
> Reglas de RLS de `CLAUDE.md` que este módulo respeta: nunca `set_config` a mano (se usa
> `set_tenant_context` / `set_system_context`); las dos tablas nuevas llevan `ENABLE` + `FORCE` y la
> política `tenant_isolation`; el relleno de la migración levanta el `FORCE` solo mientras corre.

> [!WARNING]
> **Numeración de migraciones.** En esta rama la 014 ya es `014_tenant_external_ref.py` (sedes de
> Appits) y este módulo es la **015**. El Módulo 09
> ([DT de gestión de usuarios](../09_gestion_usuarios/DT_gestion_usuarios.md)) documenta *su*
> migración como «014»: al implementarla, la de usuarios debe numerarse **016** y apuntar a la 015.
> Ver §11 y el riesgo en el sprint.

---

## 1. Estado de partida (código real a 2026-11-04)

| Pieza | Dónde | Situación |
|---|---|---|
| Saldos | `app/models/stock_balance.py`, índice `idx_stock_product_zone_lot` | Clave `(tenant, producto, zona, lote)`. Sin bin ni proveedor |
| Lotes | `app/models/batch.py`, `uq_batches_tenant_product_number` | Único por producto + número. Sin proveedor |
| Ledger | `app/models/inventory_ledger.py` | Tenía `lot_number`. Sin bin ni proveedor; `transaction_id` obligatorio en la respuesta |
| Reservas | `app/services/reservation.py` | Un solo `UPDATE … WHERE product_id AND zone_id` por ítem; sin lote ni desglose |
| Confirmación | Mismo servicio | Escribía el ledger sin `transaction_id` → `GET /v1/ledger` daba `500` |
| Expiración | `app/main.py` | Mismo `UPDATE` por producto + zona |
| Bins | `app/models/bin.py`, migración 010 | Existían; ningún movimiento ni saldo los usaba |
| Portal | `web_frontend/app/main.py` | Páginas Productos y Stock separadas; estilos por defecto de NiceGUI |
| Migraciones | `alembic/versions/` | Última: `014_tenant_external_ref.py` |

---

## 2. Resumen de Cambios por Superficie

Todos los campos son opcionales (C-1). El detalle campo a campo, con ejemplos reales de request y
response, está en el [contrato de integración](../../integracion/trazabilidad_lotes_ubicaciones.md);
aquí no se duplica.

| Endpoint | Entrada nueva | Respuesta nueva | Fichero |
|---|---|---|---|
| `POST /v1/transactions/receipts` | `supplier_id`, `items[].bin_id`, `items[].supplier_id` | `document_number` | `inventory.py` |
| `POST /v1/transactions/issues` | `items[].bin_id`, `items[].supplier_id` | — | `inventory.py` |
| `POST /v1/transactions/transfers` | `items[].from_bin_id`, `to_bin_id`, `supplier_id` | — | `inventory.py` |
| `POST /v1/transactions/adjustments` | `items[].bin_id`, `items[].supplier_id` | — | `inventory.py` |
| `POST /v1/reservations` | `items[].lot_number`, `bin_id`, `supplier_id` | `items[].allocations[]` | `reservation.py` |
| `POST /v1/reservations/{id}/confirm` | — (cuerpo igual) | `allocations[].confirmed_qty` | `reservation.py` |
| `GET /v1/stock/balances` | `lot_number`, `bin_id`, `supplier_id` | `bin_id`, `bin_code`, `bin_name`, `supplier_id`, `expiry_date` | `inventory.py` |
| `GET /v1/ledger` | `lot_number`, `zone_id`, `bin_id`, `supplier_id`, `reference_id`, `document_number`, `date_from`, `date_to` | los de saldos + `document_number`; `transaction_id` opcional | `inventory.py` |
| `POST/GET /v1/batches` | `supplier_id` | `supplier_id` | `batch.py` |
| `GET /admin/tenants/{id}/suppliers` | — | lista de proveedores (incluye inactivos) | `admin_products.py` |

---

## 3. Servicios — dónde vive la lógica

Los endpoints validan y delegan; la lógica va en servicios (patrón del proyecto).

| Servicio | Funciones |
|---|---|
| `app/services/traceability.py` (nuevo) | `get_bin_in_zone`, `get_supplier_of_tenant`, `require_lot`, `balance_supplier`, `ensure_batch`, `next_document_number`, `eq_or_null`, `opt_str` |
| `app/services/inventory.py` | `_get_or_create_balance`, `_find_existing_balance`, `_make_ledger_entry`, `process_receipt/issue/transfer/adjustment`, `query_stock_balances`, `query_ledger` |
| `app/services/reservation.py` (reescrito) | `_candidate_balances`, `create_reservation`, `_get_items`, `confirm_reservation`, `cancel_reservation`, `expire_reservation`, `_item_allocations` (rama legacy) |
| `app/services/batch.py` | Duplicado por proveedor |

### 3.1 Validaciones compartidas (`traceability.py`)

| Función | Qué hace | Error |
|---|---|---|
| `get_bin_in_zone(db, bin_id, zone_id, tenant_id)` | El bin existe, es del tenant, de esa zona y está activo | `404` si no existe o es de otro tenant; `422` si es de otra zona o está inactivo |
| `get_supplier_of_tenant(db, supplier_id, tenant_id)` | El proveedor es del tenant | `404` |
| `require_lot(product, lot_number)` | Con `track_lots`, exige lote | `422` "El producto {sku} maneja lotes (track_lots = true): el ítem debe incluir lot_number." |
| `balance_supplier(lot, supplier)` | Devuelve el proveedor **solo si hay lote** (RN-054-2) | — |
| `ensure_batch(...)` | Crea o reutiliza el lote heredando proveedor y vencimiento | — |
| `next_document_number(db, tenant_id, doc_type="RECEIPT", prefix="E")` | Siguiente `E-%06d` por tenant | — |

---

## 4. Contratos API

Formato de error: el del handler global (`detail`, `error_code`, `timestamp`, `request_id`).

### 4.1 Identidad del lote y clave del saldo

```text
Lote   = (tenant, producto, COALESCE(proveedor, nil), número)
Saldo  = (tenant, producto, zona, COALESCE(bin, nil), COALESCE(lote, 'N/A'), COALESCE(proveedor, nil))
```

`balance_supplier` garantiza que, sin lote, el proveedor de la clave es `NULL`: una salida sin lote
nunca queda ambigua. Con un lote repetido de dos proveedores en la misma ubicación,
`_find_existing_balance` responde `409` pidiendo `supplier_id`.

### 4.2 Códigos de error

| Código | Cuándo |
|---|---|
| `404` | `bin_id` o `supplier_id` inexistente o de otro tenant |
| `422` | Bin de otra zona o inactivo · falta `lot_number` con `track_lots` · confirmar más de lo reservado |
| `409` | Mismo lote de dos proveedores sin `supplier_id` · mismo proveedor repite número de lote · stock disponible insuficiente · lote de otro tenant en una reserva (sin stock) |

### 4.3 Consecutivo de entradas

`next_document_number` hace un `INSERT … ON CONFLICT (tenant_id, doc_type) DO UPDATE SET last_value =
last_value + 1 RETURNING last_value`. El `UPSERT` **bloquea la fila hasta el commit**, así que dos
entradas simultáneas del mismo tenant se serializan, y un rollback devuelve el número. El valor se
guarda en `transactions.document_number` y en cada línea del ledger de esa entrada.

---

## 5. Reservas: algoritmo y concurrencia

### 5.1 Crear

1. Producto del ítem → `track_lots`.
2. `_candidate_balances` selecciona los saldos de producto + zona con `available_qty > 0`, filtrados
   por `lot_number`/`bin_id`/`supplier_id` si se pidieron, con `FOR UPDATE OF sb`.
3. Orden de consumo:

   | Producto | `ORDER BY` |
   |---|---|
   | Con `track_lots` | sin lote al final · vencimiento ASC (nulos al final) · primera entrada ASC · lote · sin ubicar primero · código de bin · id |
   | Sin `track_lots` | sin lote primero · sin ubicar primero · código de bin · primera entrada ASC · id |

   El vencimiento y la primera entrada salen de `batches` y, para lotes anteriores a que las entradas
   crearan lotes, del ledger (`_LOT_EXPIRY`, `_LOT_FIRST_IN`).
4. Se recorre el orden repartiendo la cantidad. Cada tramo es una fila de `reservation_allocations`
   (`seq`, `stock_balance_id`, lote, bin, proveedor, `quantity`) y suma `reserved_qty` / resta
   `available_qty` de **ese** saldo. Un diccionario `claimed` evita apartar dos veces lo mismo dentro
   de una reserva con varios ítems del mismo producto.
5. Si no alcanza → `409`.

### 5.2 Confirmar, cancelar y expirar

| Operación | Efecto |
|---|---|
| `confirm_reservation` | Despacha en el orden de `seq`. Crea una `Transaction` de salida (`reference` `RESERVATION_CONFIRM` o el `issue_reference`) y un `ISSUE` en el ledger por asignación, con `reference_id` = el de la reserva y costo = `current_cpp`. Más de lo reservado → `422`. Menos → libera lo sobrante |
| `cancel_reservation` | Devuelve a `available_qty` exactamente `quantity - confirmed_qty` de cada asignación |
| `expire_reservation(db, tenant_id, reservation_id)` | Igual que cancelar, con estado `EXPIRED`. **No hace commit:** lo hace el bucle de `main.py` |
| `_item_allocations` | Reservas anteriores a la 015 (sin asignaciones): opera contra el saldo de producto + zona, como antes |

### 5.3 Concurrencia

`FOR UPDATE OF sb` serializa dos reservas que compiten por el mismo saldo. La prueba
`test_reservation_locks_the_balances_it_allocates` es determinista: toma `_candidate_balances` en una
sesión y comprueba, con `SET LOCAL lock_timeout`, que una segunda sesión no puede tocar esas filas.
Se verificó por mutación que **falla si se quita el `FOR UPDATE`** (una primera versión con
concurrencia real pasaba también sin el candado y por eso se descartó).

---

## 6. Migración 015

`alembic/versions/015_lot_location_traceability.py` — `revision = "015"`, `down_revision = "014"`.

### 6.1 `upgrade()`

| Bloque | Qué hace |
|---|---|
| `batches` | `supplier_id`; quita `uq_batches_tenant_product_number`; crea `uq_batches_tenant_product_supplier_number` con `COALESCE`; índice por proveedor |
| `stock_balances` | `bin_id`, `supplier_id`; quita `idx_stock_product_zone_lot`; crea `idx_stock_product_zone_bin_lot_supplier`; índices por bin y lote |
| `inventory_ledger` | `bin_id`, `supplier_id`; índices por lote, bin y `reference_id`. Solo columnas nuevas |
| `reservation_items` | `lot_number`, `bin_id`, `supplier_id` |
| `reservation_allocations` | Tabla nueva, índices `(item, seq)` y `(tenant, lote)`, RLS |
| `transactions` / `document_sequences` | `document_number`, índice único parcial; tabla de secuencias con RLS |
| Relleno | Numera las entradas históricas (`row_number()` por tenant, orden `created_at, id`) y carga `document_sequences` |

### 6.2 Relleno bajo RLS

`transactions` tiene `FORCE ROW LEVEL SECURITY`. El relleno hace `NO FORCE` sobre `transactions` y
`document_sequences`, ejecuta el `UPDATE`/`INSERT` y vuelve a `FORCE`. Un superusuario habría ignorado
las políticas de todos modos; así también funciona con un rol dueño sin superusuario. Corre con
`MIGRATION_DATABASE_URL`, como todas.

### 6.3 `downgrade()`

Revierte todo en orden inverso y se probó en ciclo `down` → `up` sobre la base de desarrollo.
**Dos avisos:**

- Volver a la clave anterior del saldo y del lote **falla** si ya hay saldos o lotes que solo se
  distinguen por bin o proveedor; hay que consolidarlos antes de bajar.
- Bajar elimina `bin_id`, `supplier_id`, las asignaciones y los consecutivos: se pierde lo escrito
  después de subir.

### 6.4 Compatibilidad con datos existentes

Las filas anteriores quedan con `bin_id` y `supplier_id` en `NULL` y conservan exactamente su clave.
El ledger no se modifica (C-4). Las reservas anteriores siguen funcionando por la rama legacy.

---

## 7. Portal (`web_frontend/`)

### 7.1 Estructura

| Fichero | Contenido |
|---|---|
| `app/theme.py` (nuevo) | Paleta, CSS (tarjetas, píldoras, navegación, tablas, rejilla `.mn-loc` del desglose), `shell()` con la barra lateral, `category_expansion`, `breadcrumb`, `sub_header`, `fmt_date`, `plural`. `SHOW_STOCK_PAGE = False` |
| `app/main.py` | Páginas rediseñadas; en Productos: `_load_locations`, `_all_balances`, `_zone_type_label`, `_qty`, `_StockDialogs`, `_PRODUCT_ROW_SLOT`, `page_products` |
| `app/api.py` | `list_stock(..., page, page_size)` paginado; `list_suppliers(token, tenant_id)` |

### 7.2 Decisiones

- **Opción 1 (Productos + existencias).** Si no gusta, la opción 2 estaba diseñada y, si tampoco,
  `SHOW_STOCK_PAGE = True` devuelve Stock al menú sin tocar nada más.
- **Datos del desglose:** `_all_balances` pagina de a 200 (máximo del endpoint). Almacenes y zonas se
  cargan una vez; los proveedores desde `GET /admin/tenants/{id}/suppliers` (si falla, el desglose
  sigue y muestra "Proveedor no encontrado").
- **Tipo de zona:** `_zone_type_label` reutiliza `ZONE_TYPES` de la pantalla de Almacenes, sin la explicación.
- **Estilos:** las capas `!important` de Quasar (p. ej. `text-primary`) no se sobrescriben con CSS sin
  capa: el botón *Salir* es un `<button>` nativo y el relleno de la expansión se corrige sobre
  `.nicegui-expansion-content`.
- **Tabla ancha:** la rejilla del desglose tiene `min-width` y `overflow-x: auto`; en las tablas de
  stock, `wrap-cells` y acciones `text-no-wrap` evitan el desborde horizontal.
- **Qué no hace (aún):** capturar ubicación, proveedor ni vencimiento en los formularios; mostrar el
  vencimiento (se quitó del desglose a petición mientras tanto, aunque el API ya lo devuelve).

---

## 8. Tests

Todos en `core_backend/tests/test_lot_location_traceability.py` (27 tests). Cada uno crea sus datos
con tenants de prueba y la base hace rollback; no tocan datos reales.

| Grupo | Casos |
|---|---|
| Compatibilidad (C-1, C-2) | Entrada y saldos sin campos nuevos · reserva confirmar/cancelar sin campos nuevos · reserva anterior a la 015 · ledger acepta filas sin `transaction_id` |
| Bins | Entrada en bin mantiene saldo aparte · bin de otra zona o inactivo · salida, ajuste y traslado por bin · traslado valida cada bin contra su zona |
| Proveedores | Mismo lote de dos proveedores separado · la entrada crea el lote heredando proveedor y vencimiento · número único por producto + proveedor |
| Reservas | FEFO · FIFO · reparto entre lotes · lote y bin explícitos · confirmar emite un `ISSUE` por lote con la orden · confirmación parcial · bloqueo de saldos · confirmar de más → `422` · cancelar y expirar liberan cada lote |
| Consulta | Filtros de saldos (lote, bin, proveedor, vencimiento) · filtros y campos del ledger |
| Lote obligatorio | `track_lots` exige lote en entrada, ajuste y traslado · la reserva sin lote no se rechaza |
| Consecutivo | `document_number` consecutivo y buscable |
| Admin y aislamiento | Proveedores del tenant desde el admin · bin, proveedor y lote de otro tenant rechazados |

**Resultado (2026-11-05):** `27 passed` en el archivo; la suite completa dio `373 passed, 1 skipped`
antes de integrar `origin/main` y **`386 passed, 1 skipped`** después (los 13 tests nuevos son de Deiby);
los 346 tests anteriores pasan **sin modificarse** (prueba de C-1). `ruff check app/` y `mypy app/`
(116 ficheros) sin errores, ejecutados dentro del contenedor `inv-api`.

Comando (el pytest corre dentro del contenedor, donde está la base de datos):

```bash
docker exec inv-api sh -c "cd /app && python -m pytest -q tests/test_lot_location_traceability.py"
```

---

## 9. Qué cambió en el código existente (impacto)

| Lugar | Cambio | Riesgo |
|---|---|---|
| `services/inventory.py` | `_get_or_create_balance` y `_make_ledger_entry` ganan `bin_id` y `supplier_id` (por defecto `None`) | Bajo: llamadas existentes no cambian |
| `services/reservation.py` | Reescrito entero | **Medio:** es el cambio de mayor superficie. Cubierto por 12 tests de reservas |
| `main.py` | El bucle de expiración llama a `expire_reservation` | Bajo |
| `schemas/inventory.py` | `LedgerEntryResponse.transaction_id` pasa a `UUID \| None` | Bajo: solo relaja la respuesta |
| `services/supplier.py` | `list_suppliers(is_active: bool \| None = True)` | Bajo: el valor por defecto conserva el comportamiento |
| `models/batch.py` | Ya no es único por producto + número | Medio: depende de la migración 015 |

---

## 10. Deuda conocida (no corregida)

| # | Qué | Dónde | Efecto |
|---|---|---|---|
| 1 | Los **conteos cíclicos** leen y escriben saldos por producto + zona | `services/cycle_count.py` | Con varios lotes o bins en la zona fijan **todas** esas filas al valor contado. Antes no se notaba: había una fila por zona |
| 2 | `api_scopes.md` usa el dominio viejo `https://api.micronuba.com` | `doc/integracion/api_scopes.md` | Documentación desactualizada |
| 3 | El portal no captura ubicación, proveedor ni vencimiento | `web_frontend/app/main.py` | Se asignan por API |
| 4 | La copia de la guía en `D:\Desktop\trazabilidad_lotes_ubicaciones.md` quedó anterior a `expiry_date` en saldos | Fuera del repo | Reenviar la versión del repo |
| 5 | Selección de ícono por categoría: es heurística de nombre, no un dato | Portal | Decisión pendiente si se quiere elegir a mano |

---

## 11. Integración y despliegue (lo hace Deiby Moreno)

1. **`origin/main` ya está integrado en la rama (hecho el 2026-11-05).** El único conflicto fue
   `web_frontend/app/main.py`: `origin/main` añadió el límite de intentos de login (`page_login(request)`,
   IP del navegador, `api.admin_login(..., client_ip)` y el mensaje `429`) justo donde esta rama
   rediseñó `page_login`. Se resolvió conservando el diseño nuevo **más** esas líneas. `CLAUDE.md`,
   `api.py` y `deps.py` se mezclaron solos. Si `origin/main` avanza antes del merge, repetir `git fetch`.
2. **Orden de migraciones:** `014` (sedes) → `015` (este módulo) → la migración de usuarios del
   Módulo 09, que debe renombrarse **016** y apuntar a `down_revision = "015"`.
3. **Antes de migrar en producción:** respaldar la base. La 015 numera las entradas históricas: en
   tenants con muchas entradas, medir el tiempo en staging.
4. Staging primero (rama `develop`): `alembic upgrade head` con `MIGRATION_DATABASE_URL`, recrear `api`,
   `worker` (código de reservas) y `admin-portal`. Verificar el flujo de Appits: entrada con lote y
   proveedor → reserva → confirmación → `GET /v1/ledger?lot_number=…`.
5. Avisar a Appits **antes** de producción de los tres cambios de comportamiento (RF-061) y enviarle
   el contrato. Verificar con ellos si hacen entradas sin lote de productos con `track_lots`.
6. Prod: fuera del horario de oficina de Colombia y avisando a infra del commit y la hora (hay
   tenants reales).
7. Reversa: `alembic downgrade -1` solo si no se escribió stock con bin o proveedor distinto (§6.3).
