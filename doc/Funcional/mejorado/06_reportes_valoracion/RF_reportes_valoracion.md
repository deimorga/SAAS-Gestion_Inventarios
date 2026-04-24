# Módulo 06: Reportes y Valoración Contable

**RF cubiertos:** RF-029 a RF-032  
**Prioridad MVP:** P1 (Segundo Corte)  
**Documento padre:** [DEFINICION_SAAS.md](../00_definicion-solucion_saas/DEFINICION_SAAS.md)

---

## Contexto y Alcance

Este módulo convierte los datos transaccionales en **información de valor para la toma de decisiones**. Proporciona el Kardex histórico, los snapshots de valoración y las alertas de reabastecimiento. Es consumido por áreas contables, gerencia y sistemas ERP.

---

## Requerimientos Funcionales

### RF-029: Consulta de Kardex Histórico

- **ID:** RF-029 | **Prioridad:** P1
- **Descripción:** Consultar la historia completa de movimientos de un producto en un almacén, mostrando tipo de movimiento, cantidad, costo, saldo resultante, referencia y ejecutor. Equivale al "libro mayor" del inventario.
- **Flujo Principal:**
  1. El sistema recibe: `product_id`, `warehouse_id` (opcional), rango de fechas, tipo de movimiento (opcional).
  2. Consulta el INVENTORY_LEDGER con los filtros y calcula el saldo acumulado movimiento a movimiento.
  3. Retorna una lista paginada con cada movimiento y su saldo resultante.
- **Reglas de Negocio:**
  - RN-029-1: El Kardex es de solo lectura — no se puede editar ni eliminar un registro.
  - RN-029-2: Los registros de anulación se muestran como contrapartidas (no se ocultan).
  - RN-029-3: Se puede exportar en formato CSV o JSON.

### RF-030: Balance Snapshot (Estado del Inventario en un Punto del Tiempo)

- **ID:** RF-030 | **Prioridad:** P1
- **Descripción:** Consultar una "foto" del inventario en un momento dado: stock físico, reservado y disponible, con valoración económica (cantidad × CPP).
- **Flujo Principal:**
  1. El sistema recibe: `snapshot_date` (opcional, por defecto "ahora"), filtros opcionales (almacén, categoría).
  2. Si es "ahora" → consulta directamente STOCK_BALANCE.
  3. Si es una fecha histórica → reconstruye el saldo recorriendo el LEDGER hasta esa fecha.
  4. Retorna tabla con: producto, almacén, stock físico, reservado, disponible, CPP, valor total (cantidad × CPP).
- **Reglas de Negocio:**
  - RN-030-1: El snapshot "ahora" es una consulta rápida directa. El histórico puede tardar y se procesa de forma asíncrona si abarca muchos productos.
  - RN-030-2: El valor total de inventario es la suma de (physical_qty × unit_cost) de todos los STOCK_BALANCE.

### RF-031: Alertas de Stock Bajo y Punto de Reorden

- **ID:** RF-031 | **Prioridad:** P1
- **Descripción:** Evaluar continuamente los niveles de stock contra los umbrales mínimos definidos por producto (reorder_point). Cuando el stock disponible cae por debajo del umbral, generar alerta interna y webhook.
- **Flujo Principal:**
  1. Después de cada operación que modifique `available_qty`, el sistema compara contra el `reorder_point` del producto.
  2. Si `available_qty < reorder_point` y la política `low_stock_alert_enabled = true` → genera alerta.
  3. La alerta incluye: producto, almacén, stock disponible, reorder_point, proveedores sugeridos (si existen, RF-011).
  4. Si el tenant tiene webhooks configurados (RF-033) para el evento `stock.low`, dispara la notificación.
- **Reglas de Negocio:**
  - RN-031-1: No se genera alerta duplicada si el stock ya estaba por debajo del umbral (solo al cruzar el umbral).
  - RN-031-2: El reorder_point = 0 desactiva alertas para ese producto específico.

### RF-032: Valoración Contable Consolidada

- **ID:** RF-032 | **Prioridad:** P1
- **Descripción:** Generar un reporte de valoración del inventario por método contable (CPP o PEPS según configuración del tenant), agrupable por categoría, almacén o producto.
- **Flujo Principal:**
  1. El sistema recibe: `group_by` (categoría, almacén, producto), rango de fechas, método de valoración.
  2. Calcula el valor total del inventario según el método del tenant.
  3. Retorna tabla consolidada con: agrupación, cantidad total, valor unitario promedio, valor total.
- **Reglas de Negocio:**
  - RN-032-1: El reporte CPP usa el costo promedio ponderado vigente de cada producto.
  - RN-032-2: El reporte PEPS calcula el valor basándose en el costo de los lotes más antiguos en stock.
  - RN-032-3: El reporte se puede exportar en CSV, JSON y PDF.

---

## Historias de Usuario

### HU-REP-001: Consultar Kardex de un Producto

- **Narrativa:** Como **administrador del tenant**, quiero ver todos los movimientos de mi producto "Monitor 24 pulgadas" en el último mes, para auditar una discrepancia de stock.
- **Criterios de Aceptación:**
  1. **Dado** que consulto el Kardex del producto con rango de fechas, **Cuando** hubo 15 movimientos, **Entonces** veo cada uno con tipo, cantidad, costo, saldo resultante y quién lo ejecutó.
  2. **Dado** que intento eliminar un registro del Kardex, **Cuando** envío la petición, **Entonces** recibo `405 Method Not Allowed`.
  3. **Dado** que exporto el Kardex en CSV, **Cuando** lo descargo, **Entonces** contiene todas las columnas del reporte.

### HU-REP-002: Obtener Valoración del Inventario

- **Narrativa:** Como **sistema ERP (Contabilidad)**, quiero obtener el valor total del inventario agrupado por categoría, para registrarlo en los estados financieros mensuales.
- **Criterios de Aceptación:**
  1. **Dado** que consulto la valoración agrupada por categoría, **Cuando** el tenant usa CPP, **Entonces** recibo el valor de cada categoría calculado con el CPP de cada producto.
  2. **Dado** que consulto la valoración total, **Cuando** sumo todas las categorías, **Entonces** coincide con la suma de (physical_qty × unit_cost) de todos los STOCK_BALANCE.

---

## Matriz de Endpoints

| Método | Endpoint | Descripción | Scope |
|--------|----------|-------------|-------|
| `GET` | `/v1/reports/kardex` | Consultar Kardex (filtrable) | `READ_INVENTORY` |
| `GET` | `/v1/reports/kardex/export` | Exportar Kardex (CSV/JSON) | `READ_INVENTORY` |
| `GET` | `/v1/reports/snapshot` | Balance Snapshot actual o histórico | `READ_INVENTORY` |
| `GET` | `/v1/reports/valuation` | Valoración contable consolidada | `READ_INVENTORY` |
| `GET` | `/v1/reports/valuation/export` | Exportar valoración (CSV/JSON/PDF) | `READ_INVENTORY` |
| `GET` | `/v1/alerts/low-stock` | Listar alertas de stock bajo activas | `READ_INVENTORY` |
